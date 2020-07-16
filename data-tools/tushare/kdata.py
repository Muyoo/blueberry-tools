# encoding:utf8
import tushare as ts
import datetime
import time
import pandas as pd
import psycopg2 as pg
import mmh3
import json
import sys

TOKEN = 'cdc7a2df60e6ba5449290e6eb01866500d07143b0743403e9d33a9b3'
START_DATE = datetime.datetime.strptime(sys.argv[1], '%Y-%m-%d')

VALUES_SQL_FMT = '''
    INSERT INTO values_stock_k_data(record_time, value, tag_id)
    VALUES (%s, %s, %s) ON CONFLICT (record_time, tag_id) DO NOTHING
'''

TAGS_SQL_FMT = '''
    INSERT INTO tags_stock_k_data(record_time, tags, tag_id)
    VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
'''
TAG_TIME = '2020-07-10 00:00:00'


def init_env():
    ts.set_token(TOKEN)


def load_stock():
    conn = pg.connect('dbname=blueberry user=postgres password=123456')
    cursor = conn.cursor()
    cursor.execute("SELECT code, name FROM stock_code")
    stock_code_list = cursor.fetch_all()
    stock_dic = {}
    for stock in stock_code_list:
        stock_dic[stock[0]]


def load_history(filename):
    conn = pg.connect('dbname=blueberry user=postgres password=123456')
    cursor = conn.cursor()
    with open(filename, 'r') as reader:
        title = reader.readline().strip().split(',')[1:]
        last_record_time = ''
        for line in reader:
            items = line.strip().split(',')[1:]
            record_time = datetime.datetime.strptime(
                items[title.index('trade_date')], '%Y%m%d')
            if record_time < START_DATE:
                continue

            record_time = record_time.strftime('%Y-%m-%d 00:00:00')
            
            code = items[title.index('ts_code')].split('.')[0]

            if last_record_time != record_time:
                print(record_time)
                last_record_time = record_time
                conn.commit()

            for metric in title[2:]:
                tag_id = mmh3.hash('%s-%s' % (code, metric))
                cursor.execute(VALUES_SQL_FMT, (record_time, float(
                    items[title.index(metric)]), tag_id))
                cursor.execute(TAGS_SQL_FMT, (TAG_TIME, json.dumps(
                    {'metric': metric, 'stockCode': code}), tag_id))

    cursor.close()
    conn.close()

def main():
    init_env()

    pro = ts.pro_api()
    days = (datetime.datetime.now() - START_DATE).days + 1
    i = 0
    trade_date = (START_DATE + datetime.timedelta(i)).strftime('%Y%m%d')
    print('Query for %s' % trade_date)
    df = pro.daily(trade_date=trade_date)
    for i in range(1, days):
        trade_date = (START_DATE + datetime.timedelta(i)).strftime('%Y%m%d')
        print('Query for %s' % trade_date)
        trade_df = pro.daily(trade_date=trade_date)
        df = df.append(trade_df)

        if i % 499 == 0:
            time.sleep(60)

    df.to_csv(path_or_buf='./k-data.csv', sep=',')


if __name__ == '__main__':
    main()
    # load_history('./k-data.csv')
    # load_stock()
    # print ('do nothing')
