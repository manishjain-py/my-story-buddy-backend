#!/usr/bin/env python3
"""
Simple database connectivity diagnostic tool
"""
import socket
import subprocess
import sys

def test_network_connectivity():
    """Test basic network connectivity to the database server."""
    host = 'database-1.cbuyybcooluu.us-west-2.rds.amazonaws.com'
    port = 3306
    
    print("=" * 60)
    print("NETWORK CONNECTIVITY DIAGNOSTIC")
    print("=" * 60)
    
    # Test DNS resolution
    print(f"\n1. Testing DNS resolution for {host}...")
    try:
        import socket
        ip = socket.gethostbyname(host)
        print(f"   ✅ DNS resolved to: {ip}")
    except Exception as e:
        print(f"   ❌ DNS resolution failed: {e}")
        return False
    
    # Test port connectivity
    print(f"\n2. Testing port connectivity to {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)  # 10 second timeout
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"   ✅ Port {port} is open and accessible")
            return True
        else:
            print(f"   ❌ Cannot connect to port {port}")
            print(f"   Error code: {result}")
            return False
    except Exception as e:
        print(f"   ❌ Connection test failed: {e}")
        return False

def test_mysql_connectivity():
    """Test MySQL-specific connectivity."""
    print(f"\n3. Testing MySQL connectivity...")
    try:
        import pymysql
        
        connection = pymysql.connect(
            host='database-1.cbuyybcooluu.us-west-2.rds.amazonaws.com',
            port=3306,
            user='admin',
            password='mystorybuddydb123',
            connect_timeout=10
        )
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            print(f"   ✅ MySQL connection successful: {result}")
            
        connection.close()
        return True
        
    except Exception as e:
        print(f"   ❌ MySQL connection failed: {e}")
        return False

def main():
    print("Database Connectivity Diagnostic Tool")
    print("Testing connection to: database-1.cbuyybcooluu.us-west-2.rds.amazonaws.com:3306")
    
    # Test network connectivity
    network_ok = test_network_connectivity()
    
    if network_ok:
        # Test MySQL connectivity
        mysql_ok = test_mysql_connectivity()
        
        if mysql_ok:
            print("\n" + "=" * 60)
            print("✅ ALL TESTS PASSED! Database is accessible.")
            print("=" * 60)
        else:
            print("\n" + "=" * 60)
            print("❌ MySQL connection failed. Check credentials.")
            print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ NETWORK CONNECTIVITY ISSUES DETECTED")
        print("=" * 60)
        print("\nPossible solutions:")
        print("1. Check RDS security group settings")
        print("2. Ensure RDS is publicly accessible")
        print("3. Verify your IP is whitelisted")
        print("4. Check VPC and subnet settings")

if __name__ == "__main__":
    main()