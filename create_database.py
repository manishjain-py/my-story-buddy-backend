#!/usr/bin/env python3
"""
Database creation script for My Story Buddy
"""
import pymysql
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_database():
    """Create the mystorybuddy database if it doesn't exist."""
    try:
        # Connect without specifying a database
        connection = pymysql.connect(
            host='database-1.cbuyybcooluu.us-west-2.rds.amazonaws.com',
            port=3306,
            user='admin',
            password='mystorybuddydb123',
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # Create database
            cursor.execute("CREATE DATABASE IF NOT EXISTS mystorybuddy CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            logger.info("Database 'mystorybuddy' created successfully!")
            
            # Show databases to confirm
            cursor.execute("SHOW DATABASES")
            databases = cursor.fetchall()
            logger.info(f"Available databases: {[db[0] for db in databases]}")
            
        connection.close()
        return True
        
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        return False

if __name__ == "__main__":
    print("Creating MySQL database 'mystorybuddy'...")
    success = create_database()
    if success:
        print("✅ Database created successfully!")
    else:
        print("❌ Failed to create database!")