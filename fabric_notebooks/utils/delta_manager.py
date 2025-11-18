"""
Delta Table Manager Module
Handles writing and managing Delta tables in Fabric lakehouse
"""

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.types import *
from pyspark.sql.functions import *
from delta.tables import DeltaTable
from typing import Optional, List
import logging


class DeltaTableManager:
    """Manages Delta table operations for raw and base layers"""
    
    def __init__(self, spark: SparkSession, lakehouse_path: str = "Tables"):
        """
        Initialize the Delta Table Manager
        
        Args:
            spark: SparkSession instance
            lakehouse_path: Base path for lakehouse tables (default: "Tables")
        """
        self.spark = spark
        self.lakehouse_path = lakehouse_path
        self.logger = logging.getLogger(__name__)
        
    def write_raw_json(
        self, 
        data: list,
        table_name: str,
        partition_cols: Optional[List[str]] = None,
        mode: str = "overwrite"
    ):
        """
        Write raw JSON data to a Delta table
        
        Args:
            data: List of dictionaries containing the raw API data
            table_name: Name of the Delta table
            partition_cols: Optional list of columns to partition by
            mode: Write mode ('overwrite', 'append', 'merge')
        """
        try:
            # Convert to DataFrame
            df = self.spark.createDataFrame(data)
            
            # Add audit columns
            df = df.withColumn("_ingested_at", current_timestamp()) \
                   .withColumn("_source", lit("G4S_API"))
            
            # Write to Delta
            writer = df.write.format("delta").mode(mode)
            
            if partition_cols:
                writer = writer.partitionBy(*partition_cols)
                
            writer.saveAsTable(table_name)
            
            self.logger.info(f"Successfully wrote {len(data)} records to {table_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to write to {table_name}: {str(e)}")
            raise
            
    def merge_delta_table(
        self,
        source_df: DataFrame,
        target_table: str,
        merge_keys: List[str],
        update_cols: Optional[List[str]] = None
    ):
        """
        Merge data into an existing Delta table (upsert)
        
        Args:
            source_df: Source DataFrame to merge
            target_table: Target Delta table name
            merge_keys: List of column names to use as merge keys
            update_cols: Optional list of columns to update (if None, updates all)
        """
        try:
            # Check if table exists
            if not self.spark.catalog.tableExists(target_table):
                # If table doesn't exist, create it
                source_df.write.format("delta").saveAsTable(target_table)
                self.logger.info(f"Created new table {target_table}")
                return
                
            # Load target table
            delta_table = DeltaTable.forName(self.spark, target_table)
            
            # Build merge condition
            merge_condition = " AND ".join([f"target.{key} = source.{key}" for key in merge_keys])
            
            # Build update dictionary
            if update_cols:
                update_dict = {col: f"source.{col}" for col in update_cols}
            else:
                update_dict = {col: f"source.{col}" for col in source_df.columns}
                
            # Perform merge
            delta_table.alias("target") \
                .merge(source_df.alias("source"), merge_condition) \
                .whenMatchedUpdate(set=update_dict) \
                .whenNotMatchedInsertAll() \
                .execute()
                
            self.logger.info(f"Successfully merged data into {target_table}")
            
        except Exception as e:
            self.logger.error(f"Failed to merge into {target_table}: {str(e)}")
            raise
            
    def delete_partition(
        self,
        table_name: str,
        partition_filter: str
    ):
        """
        Delete data from a Delta table based on a filter condition
        
        Args:
            table_name: Target Delta table name
            partition_filter: SQL condition for deletion (e.g., "academy_code = 'ABC' AND academic_year = '2324'")
        """
        try:
            delta_table = DeltaTable.forName(self.spark, table_name)
            delta_table.delete(partition_filter)
            self.logger.info(f"Deleted partition from {table_name} where {partition_filter}")
        except Exception as e:
            self.logger.error(f"Failed to delete from {table_name}: {str(e)}")
            raise
            
    def optimize_table(self, table_name: str, z_order_cols: Optional[List[str]] = None):
        """
        Optimize a Delta table with optional Z-ordering
        
        Args:
            table_name: Target Delta table name
            z_order_cols: Optional list of columns for Z-ordering
        """
        try:
            optimize_cmd = f"OPTIMIZE {table_name}"
            
            if z_order_cols:
                z_order_clause = ", ".join(z_order_cols)
                optimize_cmd += f" ZORDER BY ({z_order_clause})"
                
            self.spark.sql(optimize_cmd)
            self.logger.info(f"Optimized table {table_name}")
            
        except Exception as e:
            self.logger.error(f"Failed to optimize {table_name}: {str(e)}")
            raise
            
    def vacuum_table(self, table_name: str, retention_hours: int = 168):
        """
        Vacuum old files from a Delta table
        
        Args:
            table_name: Target Delta table name
            retention_hours: Number of hours to retain (default: 168 = 7 days)
        """
        try:
            self.spark.sql(f"VACUUM {table_name} RETAIN {retention_hours} HOURS")
            self.logger.info(f"Vacuumed table {table_name}")
        except Exception as e:
            self.logger.error(f"Failed to vacuum {table_name}: {str(e)}")
            raise


def create_base_table_from_raw(
    spark: SparkSession,
    raw_table: str,
    base_table: str,
    transformation_func,
    partition_cols: Optional[List[str]] = None
):
    """
    Helper function to create a base layer table from raw JSON data
    
    Args:
        spark: SparkSession instance
        raw_table: Source raw table name
        base_table: Target base table name
        transformation_func: Function to transform raw data to structured schema
        partition_cols: Optional list of columns to partition by
    """
    # Read raw data
    raw_df = spark.table(raw_table)
    
    # Apply transformation
    base_df = transformation_func(raw_df)
    
    # Write to base table
    writer = base_df.write.format("delta").mode("overwrite")
    
    if partition_cols:
        writer = writer.partitionBy(*partition_cols)
        
    writer.saveAsTable(base_table)
