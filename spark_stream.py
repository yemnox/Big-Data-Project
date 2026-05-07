import org.apache.hadoop.hbase.{HBaseConfiguration, TableName}; import org.apache.hadoop.hbase.client.{ConnectionFactory, Put}; import org.apache.hadoop.hbase.util.Bytes; import org.apache.spark.sql.functions._; import org.apache.spark.sql.streaming.Trigger; import org.apache.spark.sql.types._

val schema = new StructType().add("Primary Property Type", StringType).add("Total GHG Emissions (Metric Tons CO2e)", StringType)

val stream = spark.readStream.option("header", "true").schema(schema).csv("hdfs://hadoop-master:9000/project/stream_input/")

val summary = stream.filter(col("Primary Property Type").isNotNull && col("Total GHG Emissions (Metric Tons CO2e)").isNotNull).groupBy("Primary Property Type").agg(sum(col("Total GHG Emissions (Metric Tons CO2e)").cast("double")).alias("Total_Emissions"))

val query = summary.writeStream.trigger(Trigger.ProcessingTime("10 seconds")).outputMode("complete").foreachBatch { (batchDF: org.apache.spark.sql.DataFrame, batchId: Long) => { val conf = HBaseConfiguration.create(); val connection = ConnectionFactory.createConnection(conf); val table = connection.getTable(TableName.valueOf("energy_summary")); batchDF.filter(batchDF("Primary Property Type").isNotNull && batchDF("Total_Emissions").isNotNull).collect().foreach { row => val key = Option(row.getAs[String]("Primary Property Type")).getOrElse("").trim; val value = Option(row.getAs[Any]("Total_Emissions")).map(_.toString).getOrElse("0.0"); if (key.nonEmpty) { val put = new Put(Bytes.toBytes(key)); put.addColumn(Bytes.toBytes("cf"), Bytes.toBytes("total"), Bytes.toBytes(value)); table.put(put) } }; connection.close(); println(s"Batch $batchId written to HBase successfully") } }.option("checkpointLocation", "hdfs://hadoop-master:9000/tmp/spark_checkpoint").start()


