# GetAppStats
#

import requests
import os
requests.packages.urllib3.disable_warnings()
from biokbase.catalog.Client import Catalog
from biokbase.narrative_method_store.client import NarrativeMethodStore
catalog = Catalog(url = "https://kbase.us/services/catalog", token = os.environ['METRICS_USER_TOKEN'])
nms = NarrativeMethodStore(url = "https://kbase.us/services/narrative_method_store/rpc")

import datetime, time

#Insures all finish times within last day.
yesterday = (datetime.date.today() - datetime.timedelta(days=1))

def get_user_app_stats(start_date=datetime.datetime.combine(yesterday, datetime.datetime.min.time()), 
                       end_date=datetime.datetime.combine(yesterday, datetime.datetime.max.time()) ):
    """ 
    Gets a data dump from the app cataloge for a certain date window.   
    If no statt and end date are entered it will default to the last 15 calendar days (UTC TIME).
    It is 15 days because it uses an underlying method that 
    filters by creation_time and not finish_time
    """
    # From str to datetime, defaults to zero time.
    if type(start_date) == str:
        start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d')
    
    # Due to issue with method filtering only by creation_time need to grab
    # all 14 days before begin date to insure getting all records with a possible 
    # finish_time within the time window specified. (14 days, 24 hours, 60 mins, 60 secs)
    begin = int(start_date.strftime('%s')) - (14 * 24 * 60 * 60) 
    end = int(end_date.strftime('%s'))
    #print("BEGIN: " + str(begin))
    #print("END: " + str(end))
        
    time_interval = {'begin': begin , 'end': end}
    stats = catalog.get_exec_raw_stats(time_interval)
    return stats

def helper_concatenation(var_pre, var_post):
    """ Simple helper method for concatenationg fields (Module and app/func name) """
    return_val = None
    if var_pre is None:
        var_pre = "Not Specified"
    if var_post is None:
        var_post= "Not Specified"
    if var_pre != "Not Specified" or var_post != "Not Specified":
        return_val = var_pre + "/" + var_post
    return return_val

def upload_user_app_stats(start_date=None, end_date=None):
    """ 
    Uploads the catalog app records into the MySQL back end.
    Uses the other functions 
    """
    import mysql.connector as mysql

    if start_date is not None or end_date is not None:
        if start_date is not None and  end_date is not None:
            app_usage_list = get_user_app_stats(start_date,end_date)
        else:
            raise ValueError("If start_date or end_date is set, then both must be set.")
    else:
        app_usage_list = get_user_app_stats()

    metrics_mysql_password = os.environ['METRICS_MYSQL_PWD']
    #connect to mysql
    db_connection = mysql.connect(
        host = "10.58.0.98",
        user = "metrics",
        passwd = metrics_mysql_password,
        database = "metrics"
    )

    cursor = db_connection.cursor()
    query = "use metrics"
    cursor.execute(query)

    prep_cursor = db_connection.cursor(prepared=True)
    user_app_insert_statement = "insert into user_app_usage " \
                                "(job_id, username, app_name, "\
                                "start_date, finish_date, "\
                                "run_time, is_error, git_commit_hash, func_name) " \
                                "values(%s,%s,%s,FROM_UNIXTIME(%s),FROM_UNIXTIME(%s),%s,%s,%s,%s);"

    num_rows_inserted = 0;
    num_rows_failed_duplicates = 0;
    num_no_job_id = 0;
    #insert each record.
    for record in app_usage_list:
        is_error = False
        if record['is_error'] == 1:
            is_error = True
        if 'job_id' not in record:
            num_no_job_id += 1

        input = (record.get('job_id'),record['user_id'], 
                 helper_concatenation(record["app_module_name"], record["app_id"]),
                 record['exec_start_time'], record['finish_time'], (record['finish_time'] - record['exec_start_time']),
                 is_error, record['git_commit_hash'], helper_concatenation(record["func_module_name"], record["func_name"]))
        #Error handling from https://www.programcreek.com/python/example/93043/mysql.connector.Error
        try:
            prep_cursor.execute(user_app_insert_statement,input)
            num_rows_inserted += 1
        except mysql.Error as err:
            num_rows_failed_duplicates += 1

    db_connection.commit()
    print("Number of app records inserted : " + str(num_rows_inserted))
    print("Number of app records duplicate : " + str(num_rows_failed_duplicates))
    print("Number of no job id records : " + str(num_no_job_id))
    print("App Usage Record_count: " + str(len(app_usage_list)))
    return 1;

