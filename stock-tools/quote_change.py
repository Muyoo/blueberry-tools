# encoding: utf8

import psycopg2 as pg
import json
import pdb
import sys
import time
import requests
import re
from datetime import datetime

STOCK_LIST_SQL = '''
    SELECT code, name FROM stock_code 
    WHERE (code LIKE '6%' OR code LIKE '00%')
    -- WHERE code = '002498' 
        AND name NOT LIKE '*ST%'
'''

CHANGE_SQL_FMT = '''
    SELECT date_trunc('day', record_time) AS "day", value 
    FROM stock_k_data
    WHERE record_time >= to_timestamp(1262275200) 
        AND metric = 'pct_chg' AND tag_stock_code(tags) = '%s'
    ORDER BY "day" ASC
'''
PCT_CHANGE_THRESHOLD = 9.0
PRICE_THRESHOLD = 40.0
PROBABILITY_THRESHOLD = 0.85
STATISTIC_BASIC_COUNT = 15


def load_from_csv(filename):
    print('Loading stocks history k-data...')
    records_dic = {}
    with open(filename, 'r') as reader:
        title = reader.readline().strip().split(',')[1:]
        pct_chg_idx = title.index('pct_chg')
        open_idx = title.index('open')
        code_idx = title.index('ts_code')
        is_title = True
        for line in reader:
            if is_title:
                is_title = False
                continue

            items = line.strip().split(',')[1:]
            pct_chg = float(items[pct_chg_idx])
            code = items[code_idx]
            open_price = float(items[open_idx])

            if code not in records_dic:
                records_dic[code] = []

            records_dic[code].append((pct_chg, open_price))

    print('Complated loading history k-data')

    return records_dic


def d3_d4_change(filename, output_filename):
    records_dic = load_from_csv(filename)
    values_list = []
    for code, records in records_dic.items():
        valid_stock_code = (code.startswith('6') and not code.startswith('68')) or code.startswith('00') #or code.startswith('30')
        if not valid_stock_code:
            continue

        total = 0
        d3 = 0
        d4 = 0
        i = 0
        length = len(records)
        for change, open_price in records:
            if change < PCT_CHANGE_THRESHOLD:
                i += 1
                continue

            pre_change, _ = records[i - 1]
            if pre_change <= 0:
                i += 1
                continue

            total += 1
            if i + 1 < length:
                d_3_change, _ = records[i+1]
                if d_3_change > 0:
                    d3 += 1
            else:
                break

            if i + 2 < length:
                d_4_change, _ = records[i+2]
                if d_4_change > 0:
                    d4 += 1
            else:
                break

            i += 1

        values_list.append((code, total, d3, d4))

    sorted_list = sorted(
        values_list, key=lambda x: x[2]/x[1] if x[1] != 0 else 0, reverse=True)
    with open(output_filename, 'w') as writer:
        for val in sorted_list:
            if val[1] == 0:
                continue
            writer.write('%s %s %s %s %s\n' %
                         (val[0], val[2]/val[1], val[1], val[2], val[3]))

    return records_dic


# 3日交易
# 分母：涨停日 D，D-1 涨幅 (0, 0.1)，D+1 涨跌幅 (-0.1, 0.1)
# 分子：涨停日 D，D-1 涨幅 (0, 0.1)，D+1 涨幅 (0, 0.1)
# def d3_d4_change_from_db():
#     conn = pg.connect('dbname=blueberry user=postgres password=123456')
#     cursor = conn.cursor()

#     cursor.execute(STOCK_LIST_SQL)
#     stats_dic = {}
#     stock_stats_list = []
#     for stock_info in cursor.fetchall():
#         code, name = stock_info
#         change_sql = CHANGE_SQL_FMT % code
#         cursor.execute(change_sql)

#         key = '%s-%s' % stock_info
#         stats_dic[key] = {'total': 0, 'd_3': 0, 'd_4': 0}

#         change_value_list = cursor.fetchall()
#         length = len(change_value_list)
#         i = 0
#         for record in change_value_list:
#             day, change = record
#             if change < 9.9:
#                 i += 1
#                 continue

#             pre_day, pre_change = change_value_list[i - 1]
#             if pre_change <= 0:
#                 i += 1
#                 continue

#             stats_dic[key]['total'] += 1
#             if i + 1 < length:
#                 d_3_day, d_3_change = change_value_list[i+1]
#                 if d_3_change > 0:
#                     stats_dic[key]['d_3'] += 1
#             else:
#                 break

#             if i + 2 < length:
#                 d_4_day, d_4_change = change_value_list[i+2]
#                 if d_4_change > 0:
#                     stats_dic[key]['d_4'] += 1
#             else:
#                 break

#             i += 1

#     cursor.close()
#     conn.close()

    # print(json.dumps(stats_dic))

    # total = 0
    # d_3 = 0
    # d_4 = 0
    # for key, stats in stats_dic.items():
    #     total += stats['total']
    #     d_3 += stats['d_3']
    #     d_4 += stats['d_4']

    # print(total, d_3, d_4)

# From 2000-01-01 to 2020-07-10: Total = 55869, d_3 = 37984, d_4 = 30125


def filter_change_stocks(pct_chg_file, output_filename):
    writer = open(output_filename, 'w')
    with open(pct_chg_file, 'r') as reader:
        for line in reader:
            items = line.strip().split()
            code, probability, total, d3, d4 = items
            if float(probability) > PROBABILITY_THRESHOLD and int(total) >= STATISTIC_BASIC_COUNT:
                writer.write('%s\n' % code)
    writer.close()


def pick_up_stocks(records_dic, filtered_change_filename):
    print('To pick up stocks from: ')
    filtered_codes_set = set([line.strip()
                              for line in open(filtered_change_filename, 'r')])
    writer = open('picked_up.stocks', 'w')
    for code, records in records_dic.items():
        if code not in filtered_codes_set:
            continue

        last_n_days = records[-2:]
        print('\t', code, last_n_days)
        pre_pct_change, _ = last_n_days[0]
        pct_change, open_price = last_n_days[1]
        if pre_pct_change > 0.0 and pct_change >= PCT_CHANGE_THRESHOLD:
            if open_price <= PRICE_THRESHOLD:
                writer.write('%s\n' % code)

    writer.close()


output_filename = './pct_chg_sorted.stats'
filtered_change_filename = './filtered_change.stats'


def run_train(kdata_filename):
    pct_change_dic = d3_d4_change(kdata_filename, output_filename)
    filter_change_stocks(output_filename, filtered_change_filename)

    pick_up_stocks(pct_change_dic, filtered_change_filename)
    # candidates = [code.strip() for code in open(filter_change_stocks, 'r')]


def run_monitor():
    regx_pattern = re.compile('"(.*)"')
    url_fmt = 'http://hq.sinajs.cn/list=%s'
    candidates = set([])
    with open(filtered_change_filename, 'r') as reader:
        for line in reader:
            code, exchange = line.strip().split('.')
            candidates.add('%s%s' % (exchange.lower(), code))

    while True:
        hour = datetime.now().strftime('%H')
        if hour > '16':
            print('Marcket is closed. Exit.')
            break

        for stock in candidates:
            stock_url = url_fmt % stock
            data = requests.get(stock_url).text.strip()
            data = regx_pattern.search(data).groups()[0]

            name, open_price, pre_close_price, current_price = data.split(',')[
                :4]
            if float(pre_close_price) <= 0 or float(open_price) <= 0:
                continue

            pre_change = (float(pre_close_price) -
                          float(open_price)) / float(pre_close_price)
            if pre_change > 0:
                current_change = 100 * \
                    (float(current_price) - float(open_price)) / float(open_price)
                if current_change > 7:
                    print(name, stock, current_price, current_change)

        time.sleep(5)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(
            'Usage: \n\t1. quote_change.py train k-data.csv\n\t2. quote_change.py monitor')
        exit(1)

    mode = sys.argv[1]
    if mode == 'train':
        run_train(sys.argv[2])
    elif mode == 'monitor':
        run_monitor()
    else:
        print(
            'Usage: \n\t1. quote_change.py train k-data.csv\n\t2. quote_change.py monitor')
