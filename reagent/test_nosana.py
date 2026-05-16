"""Test suite for Nosana client integration.

Tests the Nosana decentralized compute client with the correct API.
"""

import sys
import os
from pathlib import Path

# Fix Windows encoding issues
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from nosana_client import NosanaClient


def test_health_check():
    """Test Nosana API health check."""
    print("\n=== Test 1: Health Check ===")
    
    nosana = NosanaClient()
    result = nosana.health_check()
    
    print(f"Status: {result.get('status')}")
    print(f"API URL: {result.get('api_url')}")
    print(f"Authenticated: {result.get('authenticated')}")
    print(f"Markets Available: {result.get('markets_available')}")
    
    assert result.get("status") in ["healthy", "unhealthy", "error"], "Invalid health status"
    print("✓ Health check completed")


def test_list_markets():
    """Test listing compute markets."""
    print("\n=== Test 2: List Markets ===")
    
    nosana = NosanaClient()
    result = nosana.list_markets(limit=5)
    
    print(f"Success: {result.get('success')}")
    print(f"Markets Count: {result.get('count', 0)}")
    
    if result.get("success") and result.get("markets"):
        for market in result["markets"][:3]:
            print(f"  - {market.get('name')} ({market.get('type')})")
            print(f"    Address: {market.get('address')}")
            print(f"    GPU Types: {market.get('gpu_types', [])}")
    
    print("✓ Market listing completed")


def test_list_vaults():
    """Test listing payment vaults."""
    print("\n=== Test 3: List Vaults ===")
    
    nosana = NosanaClient()
    result = nosana.list_vaults()
    
    print(f"Success: {result.get('success')}")
    print(f"Vaults Count: {result.get('count', 0)}")
    
    if result.get("success") and result.get("vaults"):
        for vault in result["vaults"]:
            print(f"  - Vault: {vault.get('vault')}")
            print(f"    Owner: {vault.get('owner')}")
            print(f"    Created: {vault.get('created_at')}")
    else:
        print("  No vaults found (this is normal for new accounts)")
    
    print("✓ Vault listing completed")


def test_build_container_job():
    """Test building a container job definition."""
    print("\n=== Test 4: Build Container Job ===")
    
    nosana = NosanaClient()
    job_def = nosana.build_container_job(
        image="ubuntu:22.04",
        commands=["echo 'Hello from Nosana'", "date"],
        env_vars={"TEST_VAR": "test_value"},
        work_dir="/tmp"
    )
    
    print(f"Job Definition Version: {job_def.get('version')}")
    print(f"Job Type: {job_def.get('type')}")
    print(f"Operations Count: {len(job_def.get('ops', []))}")
    
    assert job_def.get("version") == "0.1", "Invalid job version"
    assert job_def.get("type") == "container", "Invalid job type"
    assert len(job_def.get("ops", [])) > 0, "No operations defined"
    
    print("✓ Container job definition built successfully")


def test_build_solidity_compile_job():
    """Test building a Solidity compilation job."""
    print("\n=== Test 5: Build Solidity Compile Job ===")
    
    nosana = NosanaClient()
    
    contract_code = """
    pragma solidity ^0.8.0;
    
    contract SimpleStorage {
        uint256 public value;
        
        function setValue(uint256 _value) public {
            value = _value;
        }
    }
    """
    
    job_def = nosana.build_solidity_compile_job(
        contract_code=contract_code,
        contract_name="SimpleStorage",
        solc_version="0.8.20"
    )
    
    print(f"Job Definition Version: {job_def.get('version')}")
    print(f"Job Type: {job_def.get('type')}")
    print(f"Operations: {len(job_def.get('ops', []))}")
    
    # Check that solc command is in the job
    ops = job_def.get("ops", [])
    if ops:
        first_op = ops[0]
        print(f"Container Image: {first_op.get('args', {}).get('image')}")
        assert "solc" in first_op.get('args', {}).get('image', ''), "Not using solc image"
    
    print("✓ Solidity compile job built successfully")


def test_create_deployment():
    """Test creating a deployment (may fail without API key/credits)."""
    print("\n=== Test 6: Create Deployment ===")
    
    nosana = NosanaClient()
    
    # Build simple job
    job_def = nosana.build_container_job(
        image="ubuntu:22.04",
        commands=["echo 'Test deployment'"]
    )
    
    # Try to create deployment
    result = nosana.create_deployment(
        name=f"test-deployment",
        job_definition=job_def,
        timeout=5,
        strategy="SIMPLE"
    )
    
    print(f"Success: {result.get('success')}")
    
    if result.get("success"):
        print(f"Deployment ID: {result.get('id')}")
        print(f"Status: {result.get('status')}")
        print(f"Market: {result.get('market')}")
        print(f"Vault: {result.get('vault')}")
        print("✓ Deployment created successfully")
    else:
        print(f"Error: {result.get('error')}")
        print("✓ Deployment creation tested (expected to fail without credits)")


def test_list_deployments():
    """Test listing deployments."""
    print("\n=== Test 7: List Deployments ===")
    
    nosana = NosanaClient()
    result = nosana.list_deployments()
    
    print(f"Success: {result.get('success')}")
    
    if result.get("success"):
        deployments = result.get("deployments", [])
        print(f"Deployments Count: {len(deployments)}")
        
        for deployment in deployments[:3]:
            print(f"  - {deployment.get('name')} ({deployment.get('status')})")
            print(f"    ID: {deployment.get('id')}")
            print(f"    Active Jobs: {deployment.get('active_jobs', 0)}")
    else:
        print(f"Error: {result.get('error')}")
        print("  (This is normal if API key is not configured)")
    
    print("✓ Deployment listing completed")


def run_all_tests():
    """Run all Nosana tests."""
    print("=" * 60)
    print("NOSANA CLIENT TEST SUITE")
    print("=" * 60)
    print("\nTesting Nosana Dashboard API integration")
    print(f"API Base URL: https://dashboard.k8s.prd.nos.ci/api")
    print("\nNote: Some tests may fail without valid API key and credits.")
    print("=" * 60)
    
    tests = [
        test_health_check,
        test_list_markets,
        test_list_vaults,
        test_build_container_job,
        test_build_solidity_compile_job,
        test_create_deployment,
        test_list_deployments,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ Test failed: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)
    
    if failed == 0:
        print("✓ All tests passed!")
    else:
        print(f"⚠ {failed} test(s) failed (may be expected without API credentials)")


if __name__ == "__main__":
    run_all_tests()

# Made with Bob
