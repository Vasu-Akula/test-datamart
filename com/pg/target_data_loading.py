from pyspark.sql import SparkSession
from pyspark.sql.types import StringType
from pyspark.sql.functions import *
import uuid
import yaml
import os.path
import utils.aws_utils as ut

if __name__ == '__main__':

    os.environ["PYSPARK_SUBMIT_ARGS"] = (
        '--jars "https://s3.amazonaws.com/redshift-downloads/drivers/jdbc/1.2.36.1060/RedshiftJDBC42-no-awssdk-1.2.36.1060.jar"\
         --packages "org.apache.spark:spark-avro_2.11:2.4.2,io.github.spark-redshift-community:spark-redshift_2.11:4.0.1,org.apache.hadoop:hadoop-aws:2.7.4" pyspark-shell'
    )

    current_dir = os.path.abspath(os.path.dirname(__file__))
    app_config_path = os.path.abspath(current_dir + "/../../" + "application.yml")
    app_secrets_path = os.path.abspath(current_dir + "/../../" + ".secrets")

    conf = open(app_config_path)
    app_conf = yaml.load(conf, Loader=yaml.FullLoader)
    secret = open(app_secrets_path)
    app_secret = yaml.load(secret, Loader=yaml.FullLoader)

    # Create the SparkSession
    spark = SparkSession \
        .builder \
        .appName("Read ingestion enterprise applications") \
        .config("spark.mongodb.input.uri", app_secret["mongodb_config"]["uri"]) \
        .getOrCreate()
    spark.sparkContext.setLogLevel('ERROR')


    def fn_uuid():
        uid = uuid.uuid4()
        return str(uid)


    fn_uuid = spark.udf.register("fn_uuid", fn_uuid, StringType())
    tgt_list = app_conf['target_list']

    for tgt in tgt_list:
        tgt_conf = app_conf[tgt]
        stg_loc = "s3a://" + app_conf["s3_conf"]["s3_bucket"] + "/" + app_conf["s3_conf"]["staging_dir"]
        if tgt == 'REGIS_DIM':
            cp_df = spark.read.parquet(stg_loc + "/" + tgt_conf["source_data"])
            cp_df.printSchema()
            cp_df.createOrReplaceTempView(tgt_conf["source_data"])

            regis_dim_df = spark.sql(tgt_conf["loading_query"])
            regis_dim_df.show(5, False)
            ut.write_into_redshift(regis_dim_df, app_secret, app_conf, "PUBLIC.REGIS_DIM")
        elif tgt == 'CHILD_DIM':
            cp_df = spark.read.parquet(stg_loc + "/" + tgt_conf["source_data"]).coalesce(1)
            cp_df.printSchema()
            cp_df.createOrReplaceTempView(tgt_conf["source_data"])

            child_dim_df = spark.sql(tgt_conf["loading_query"]).coalesce(1)
            child_dim_df.show(5, False)
            ut.write_into_redshift(child_dim_df, app_secret, app_conf, "PUBLIC.CHILD_DIM")




# spark-submit --jars "https://s3.amazonaws.com/redshift-downloads/drivers/jdbc/1.2.36.1060/RedshiftJDBC42-no-awssdk-1.2.36.1060.jar" --master yarn --packages "org.apache.spark:spark-avro_2.11:2.4.2,io.github.spark-redshift-community:spark-redshift_2.11:4.0.1,org.apache.hadoop:hadoop-aws:2.7.4" com/pg/target_data_loading.py