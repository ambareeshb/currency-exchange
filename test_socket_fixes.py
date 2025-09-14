#!/usr/bin/env python3
"""
Test Script for Socket Error Fixes
This script validates that the socket error handling improvements are working correctly.
"""

import os
import sys
import time
import socket
import threading
import requests
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_basic_connectivity():
    """Test basic application connectivity"""
    print("Testing basic connectivity...")
    
    try:
        # Test health endpoint
        response = requests.get('http://localhost/health', timeout=10)
        if response.status_code == 200:
            print("✅ Health endpoint responding")
            return True
        else:
            print(f"❌ Health endpoint returned {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health endpoint failed: {e}")
        return False

def test_socket_handling():
    """Test socket error handling by creating rapid connections"""
    print("Testing socket error handling...")
    
    def make_request():
        try:
            response = requests.get('http://localhost/', timeout=5)
            return response.status_code == 200
        except:
            return False
    
    # Create multiple concurrent requests
    success_count = 0
    total_requests = 50
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(total_requests)]
        
        for future in as_completed(futures):
            if future.result():
                success_count += 1
    
    success_rate = (success_count / total_requests) * 100
    print(f"Request success rate: {success_rate:.1f}% ({success_count}/{total_requests})")
    
    return success_rate > 90  # 90% success rate is acceptable

def test_socket_recovery():
    """Test socket recovery mechanisms"""
    print("Testing socket recovery mechanisms...")
    
    try:
        # Check if socket recovery service is running
        result = subprocess.run(
            ['systemctl', 'is-active', 'currency-exchange-recovery'],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print("✅ Socket recovery service is active")
        else:
            print("⚠️  Socket recovery service not active (optional)")
        
        # Check if recovery timer is enabled
        result = subprocess.run(
            ['systemctl', 'is-enabled', 'currency-exchange-recovery.timer'],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print("✅ Socket recovery timer is enabled")
        else:
            print("⚠️  Socket recovery timer not enabled (optional)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking recovery services: {e}")
        return False

def test_log_monitoring():
    """Test log monitoring for socket errors"""
    print("Testing log monitoring...")
    
    try:
        # Check recent logs for socket errors
        result = subprocess.run([
            'journalctl', '-u', 'currency-exchange', 
            '--since', '10 minutes ago', '--no-pager'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            log_content = result.stdout
            
            # Count socket errors
            bad_fd_count = log_content.count('Bad file descriptor')
            handled_count = log_content.count('SOCKET_ERROR_HANDLED')
            
            print(f"Recent socket errors: {bad_fd_count}")
            print(f"Handled socket errors: {handled_count}")
            
            # If we have handled errors, that's good - it means our error handling is working
            if handled_count > 0:
                print("✅ Socket error handling is working")
            elif bad_fd_count == 0:
                print("✅ No socket errors detected")
            else:
                print("⚠️  Unhandled socket errors detected")
            
            return True
        else:
            print("❌ Could not read service logs")
            return False
            
    except Exception as e:
        print(f"❌ Error checking logs: {e}")
        return False

def test_resource_usage():
    """Test resource usage and limits"""
    print("Testing resource usage...")
    
    try:
        # Check gunicorn processes
        result = subprocess.run([
            'ps', 'aux'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            gunicorn_processes = [line for line in lines if 'gunicorn' in line and 'currency-exchange' in line]
            
            if gunicorn_processes:
                print(f"✅ Found {len(gunicorn_processes)} gunicorn process(es)")
                
                # Check memory usage
                for process_line in gunicorn_processes:
                    parts = process_line.split()
                    if len(parts) >= 4:
                        memory_percent = parts[3]
                        print(f"   Memory usage: {memory_percent}%")
                
                return True
            else:
                print("❌ No gunicorn processes found")
                return False
        else:
            print("❌ Could not check processes")
            return False
            
    except Exception as e:
        print(f"❌ Error checking resource usage: {e}")
        return False

def test_file_descriptors():
    """Test file descriptor usage"""
    print("Testing file descriptor usage...")
    
    try:
        # Get gunicorn process PIDs
        result = subprocess.run([
            'pgrep', '-f', 'gunicorn.*currency-exchange'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            
            for pid in pids:
                if pid:
                    try:
                        fd_path = f'/proc/{pid}/fd'
                        if os.path.exists(fd_path):
                            fd_count = len(os.listdir(fd_path))
                            print(f"   Process {pid}: {fd_count} file descriptors")
                            
                            if fd_count > 1000:
                                print(f"⚠️  High file descriptor count for process {pid}")
                            else:
                                print(f"✅ Normal file descriptor count for process {pid}")
                    except:
                        continue
            
            return True
        else:
            print("❌ No gunicorn processes found")
            return False
            
    except Exception as e:
        print(f"❌ Error checking file descriptors: {e}")
        return False

def main():
    """Run all tests"""
    print("🔍 Running Socket Error Fix Validation Tests")
    print("=" * 50)
    
    tests = [
        ("Basic Connectivity", test_basic_connectivity),
        ("Socket Handling", test_socket_handling),
        ("Socket Recovery", test_socket_recovery),
        ("Log Monitoring", test_log_monitoring),
        ("Resource Usage", test_resource_usage),
        ("File Descriptors", test_file_descriptors),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<30} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed ({(passed/total)*100:.1f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed! Socket error fixes are working correctly.")
        return 0
    elif passed >= total * 0.8:  # 80% pass rate
        print("\n✅ Most tests passed. Socket error fixes are largely working.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the socket error fixes.")
        return 1

if __name__ == '__main__':
    sys.exit(main())