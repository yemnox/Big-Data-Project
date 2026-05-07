# TP4 — HBase + Spark Pipeline
> Big Data Lab | Chicago Energy Benchmarking Dataset  
> Stack: Hadoop 3.3.6 · HBase 2.5.8 · Spark 3.5.0 · Docker

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Step-by-Step Guide](#step-by-step-guide)
   - [1. Start the Cluster](#1-start-the-cluster)
   - [2. Start HBase](#2-start-hbase)
   - [3. Verify Everything is Running](#3-verify-everything-is-running)
   - [4. Prepare the HBase Table](#4-prepare-the-hbase-table)
   - [5. Fix Spark + HBase JAR Conflict](#5-fix-spark--hbase-jar-conflict)
   - [6. Launch Spark Shell](#6-launch-spark-shell)
   - [7. Run the Spark → HBase Pipeline](#7-run-the-spark--hbase-pipeline)
   - [8. Verify Data in HBase](#8-verify-data-in-hbase)
3. [Debugging Guide](#debugging-guide)
   - [ZooKeeper not connecting](#zookeeper-not-connecting)
   - [HBase imports fail in Spark](#hbase-imports-fail-in-spark)
   - [RegionServer keeps dying](#regionserver-keeps-dying)
   - [HDFS connection refused](#hdfs-connection-refused)
   - [Jackson version conflict](#jackson-version-conflict)
4. [Quick Reference](#quick-reference)

---

## Architecture Overview

```
chicago_energy.csv
  (stored in HDFS)
        │
        ▼
  Spark reads CSV
  groups by Primary Property Type
  sums Total GHG Emissions
        │
        ▼
  HBase Table: energy_summary
  column family: cf
  column: total
  row key: building type
```

**Required processes (check with `jps`):**

| Process | Role |
|---|---|
| NameNode | HDFS metadata |
| DataNode | HDFS data storage |
| SecondaryNameNode | HDFS checkpointing |
| ResourceManager | YARN job scheduling |
| NodeManager | YARN node agent |
| HQuorumPeer | ZooKeeper (HBase coordination) |
| HMaster | HBase master |
| HRegionServer | HBase data serving |

---

## Step-by-Step Guide

### 1. Start the Cluster

From your **host machine**, start the Docker containers:

```bash
docker start hadoop-master hadoop-slave1 hadoop-slave2
```

Enter the master container:

```bash
docker exec -it hadoop-master bash
```

Start Hadoop daemons:

```bash
./start-hadoop.sh
# or individually:
start-dfs.sh
start-yarn.sh
```

---

### 2. Start HBase

```bash
start-hbase.sh
```

If the RegionServer doesn't start automatically:

```bash
hbase-daemon.sh start regionserver
```

---

### 3. Verify Everything is Running

```bash
jps
```

Expected output (PIDs will differ):

```
XXXX NameNode
XXXX DataNode
XXXX SecondaryNameNode
XXXX ResourceManager
XXXX NodeManager
XXXX HQuorumPeer
XXXX HMaster
XXXX HRegionServer
```

Verify HBase health:

```bash
echo "status" | hbase shell 2>/dev/null | grep -E "active|servers|dead"
```

Expected:
```
1 active master, 0 backup masters, 1 servers, 0 dead, 0.0000 average load
```

Verify HDFS:

```bash
hadoop fs -ls /
```

---

### 4. Prepare the HBase Table

Enter HBase shell:

```bash
hbase shell
```

Create the table with column family `cf`:

```bash
create 'energy_summary', 'cf'
```

Verify it exists:

```bash
list
```

Exit:

```bash
exit
```

> **Note:** If the table already exists from a previous session, skip creation. Check with `list`.

---

### 5. Fix Spark + HBase JAR Conflict

This is a **one-time operation** per container session. Copy all HBase JARs into Spark's jars directory so they are loaded together without version conflicts:

```bash
cp -r $HBASE_HOME/lib/* $SPARK_HOME/jars
```

> **Warning:** Do not use `--driver-class-path` or `--jars` flags to load HBase — this causes Jackson version conflicts between HBase 2.5.8 and Spark 3.5.0. The `cp` approach is the correct method as specified in the lab.

---

### 6. Launch Spark Shell

```bash
spark-shell --master "local[*]"
```

Quick sanity check inside spark-shell:

```scala
sc.parallelize(Seq(1,2,3)).count()
// Expected: res0: Long = 3

import org.apache.hadoop.hbase.HBaseConfiguration
// Expected: import org.apache.hadoop.hbase.HBaseConfiguration
```

---

### 7. Run the Spark → HBase Pipeline

Paste each block and wait for `scala>` prompt before the next.

> **Important:** Always paste multi-line `val` assignments as a **single line** in spark-shell. Splitting across lines causes the variable to be assigned the intermediate type instead of the final result.

**Block 1 — Imports:**

```scala
import org.apache.hadoop.hbase.{HBaseConfiguration, TableName}
import org.apache.hadoop.hbase.client.{ConnectionFactory, Put}
import org.apache.hadoop.hbase.util.Bytes
import org.apache.spark.sql.functions._
```

**Block 2 — Read CSV from HDFS:**

```scala
val raw = spark.read.option("header", "true").option("inferSchema", "false").csv("/project/input/chicago_energy.csv")
```

> Replace `/project/input/chicago_energy.csv` with your actual HDFS path if different.

**Block 3 — Compute aggregation (Job 1: total GHG by building type):**

```scala
val sparkSummary = raw.filter(col("Primary Property Type").isNotNull && col("Total GHG Emissions (Metric Tons CO2e)").isNotNull && col("Total GHG Emissions (Metric Tons CO2e)") =!= "").groupBy("Primary Property Type").agg(sum(col("Total GHG Emissions (Metric Tons CO2e)").cast("double")).alias("Total_Emissions"))
```

Preview the result:

```scala
sparkSummary.show(5, false)
println(s"Total rows: ${sparkSummary.count()}")
```

**Block 4 — Write to HBase:**

```scala
val conf = HBaseConfiguration.create()
val connection = ConnectionFactory.createConnection(conf)
val table = connection.getTable(TableName.valueOf("energy_summary"))

sparkSummary.collect().foreach { row =>
  val propertyType = row.getAs[String]("Primary Property Type")
  val totalEmissions = row.getAs[Double]("Total_Emissions").toString
  val put = new Put(Bytes.toBytes(propertyType))
  put.addColumn(Bytes.toBytes("cf"), Bytes.toBytes("total"), Bytes.toBytes(totalEmissions))
  table.put(put)
}

table.close()
connection.close()
println("Successfully written to HBase energy_summary!")
```

---

### 8. Verify Data in HBase

In a separate terminal (not spark-shell):

```bash
# Count total rows
echo "count 'energy_summary'" | hbase shell 2>/dev/null | grep -E "row|=>"

# Scan first 3 rows
echo "scan 'energy_summary', {LIMIT => 3}" | hbase shell 2>/dev/null | grep -v "^20\|INFO\|WARN"

# Get a specific row
echo "get 'energy_summary', 'College/University'" | hbase shell 2>/dev/null | grep "column\|value"
```

Expected scan output:

```
Adult Education          column=cf:total, timestamp=..., value=46818.5
Ambulatory Surgical Center  column=cf:total, timestamp=..., value=87441.2
Automobile Dealership    column=cf:total, timestamp=..., value=39148.2
```

---

## Debugging Guide

### ZooKeeper not connecting

**Symptom:**
```
java.net.ConnectException: Connection refused
Attempting reconnect except it is a SessionExpiredException
```

**Diagnosis:**
```bash
jps | grep -E "HQuorumPeer|HMaster|HRegionServer"
echo "status" | hbase shell 2>/dev/null | grep -E "servers|dead"
```

**Fix:** HBase was never started or died after container restart:
```bash
start-hbase.sh
```

---

### HBase imports fail in Spark

**Symptom:**
```
error: object hbase is not a member of package org.apache.hadoop
```

**Fix:** HBase JARs not on Spark's classpath. Run this once then relaunch spark-shell:
```bash
cp -r $HBASE_HOME/lib/* $SPARK_HOME/jars
spark-shell --master "local[*]"
```

---

### RegionServer keeps dying

**Symptom:**
```
jps  # shows no HRegionServer
echo "status" | hbase shell  # shows "0 servers, 1 dead"
```

**Diagnosis — read the crash log:**
```bash
tail -80 /usr/local/hbase/logs/hbase--regionserver-hadoop-master.out
```

**Most common cause — HDFS is down:**
```bash
hadoop fs -ls /
# If this fails → fix HDFS first (see below), then restart HBase
```

**Fix:**
```bash
hbase-daemon.sh stop regionserver
hbase-daemon.sh start regionserver
# Wait 5 seconds then verify
echo "status" | hbase shell 2>/dev/null | grep servers
```

---

### HDFS connection refused

**Symptom:**
```
Call From hadoop-master/172.18.0.2 to hadoop-master:9000 failed
java.net.ConnectException: Connection refused
```

**Diagnosis:**
```bash
jps | grep NameNode
hadoop fs -ls /
```

**Fix — restart HDFS (safe, does NOT wipe data):**
```bash
stop-hbase.sh
stop-dfs.sh
start-dfs.sh        # wait 10 seconds
hadoop fs -ls /     # verify HDFS is back
start-yarn.sh
start-hbase.sh
```

> **Warning:** Never run `hdfs namenode -format` — this wipes all HDFS data.

---

### Jackson version conflict

**Symptom:**
```
JsonMappingException: Scala module 2.15.2 requires Jackson Databind version >= 2.15.0
```

**Cause:** HBase JARs loaded via `--driver-class-path` or `--jars` conflict with Spark's bundled Jackson.

**Fix:** Use the `cp` approach instead — never use `--driver-class-path` for HBase:
```bash
cp -r $HBASE_HOME/lib/* $SPARK_HOME/jars
spark-shell --master "local[*]"   # no extra flags needed
```

---

### spark-shell variable assigned wrong type

**Symptom:**
```
error: value filter is not a member of org.apache.spark.sql.DataFrameReader
```

**Cause:** Pasting a multi-line `val` block line by line — spark-shell assigns the intermediate `DataFrameReader` type to the variable before `.csv()` is reached.

**Fix:** Always paste a full `val` assignment as **one single line**:

```scala
// ❌ Wrong — paste line by line
val raw = spark.read
  .option("header", "true")
  .csv("/path/to/file.csv")

// ✅ Correct — paste as one line
val raw = spark.read.option("header", "true").csv("/path/to/file.csv")
```

---

## Quick Reference

```bash
# Start everything
docker exec -it hadoop-master bash
./start-hadoop.sh && start-hbase.sh

# Check all processes
jps

# Check HBase health
echo "status" | hbase shell 2>/dev/null | grep -E "active|servers|dead"

# Check HDFS
hadoop fs -ls /

# Fix JAR conflict (run once per container session)
cp -r $HBASE_HOME/lib/* $SPARK_HOME/jars

# Launch Spark
spark-shell --master "local[*]"

# HBase shell operations
hbase shell
> list
> describe 'energy_summary'
> count 'energy_summary'
> scan 'energy_summary', {LIMIT => 5}
> get 'energy_summary', '<row_key>'
> exit

# Read crash logs
tail -80 /usr/local/hbase/logs/hbase--regionserver-hadoop-master.out
tail -50 /usr/local/hbase/logs/hbase--regionserver-hadoop-master.log
```

---

*TP4 Big Data — INSAT RT4 — 2025/2026*
