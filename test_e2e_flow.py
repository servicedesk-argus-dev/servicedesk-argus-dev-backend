"""
E2E API lifecycle test for Argus Service Desk ITSM
Tests: Login → Create Incident → Escalate → Resolve → Close → Promote to Problem
"""
import requests
import sys
import json

BASE_URL = "http://localhost:8000/api/v1"


def run_tests():
    print("=" * 60)
    print("Argus ITSM — End-to-End API Lifecycle Test")
    print("=" * 60)

    # 1. Login
    print("\n1. Logging in as admin@argus.com ...")
    res = requests.post(f"{BASE_URL}/auth/login", json={
        "username": "admin@argus.com",
        "password": "admin123456"
    })

    if res.status_code != 200:
        print(f"   ✗ Login FAILED! {res.status_code}")
        try:
            print("   ", json.dumps(res.json(), indent=2)[:500])
        except Exception:
            print("   ", res.text[:500])
        sys.exit(1)

    data = res.json()["data"]
    token = data["access"]
    org_id = data["user"]["organization"]["id"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Organization-Id": org_id,
        "Content-Type": "application/json"
    }
    print(f"   ✓ Login OK — Org: {data['user']['organization']['name']}")
    print(f"   ✓ Roles: {data['user'].get('roles', [])}")

    # 2. Create Incident
    print("\n2. Creating an Incident ...")
    res = requests.post(f"{BASE_URL}/incidents/", headers=headers, json={
        "short_description": "API E2E Test — DB Connection Failure",
        "description": "Production database is timing out during peak hours.",
        "impact": "DEPARTMENT",
        "urgency": "HIGH",
        "category": "Database"
    })

    if res.status_code != 201:
        print(f"   ✗ Create FAILED! {res.status_code}")
        print("   ", json.dumps(res.json(), indent=2)[:500])
        sys.exit(1)

    inc = res.json()["data"]
    inc_id = inc["id"]
    inc_num = inc["number"]
    print(f"   ✓ Created: {inc_num} | Priority: {inc['priority']} | State: {inc['state']}")

    # 3. Escalate
    print(f"\n3. Escalating {inc_num} ...")
    res = requests.post(f"{BASE_URL}/incidents/{inc_id}/escalate/", headers=headers, json={
        "reason": "SLA at risk — escalating to on-call manager"
    })

    if res.status_code != 200:
        print(f"   ✗ Escalate FAILED! {res.status_code}")
        print("   ", json.dumps(res.json(), indent=2)[:500])
        sys.exit(1)

    inc = res.json()["data"]
    print(f"   ✓ Escalated: State={inc['state']} | Priority={inc['priority']}")

    # 4. Resolve (ITIL: Engineer resolves with code + notes)
    print(f"\n4. Resolving {inc_num} ...")
    res = requests.post(f"{BASE_URL}/incidents/{inc_id}/resolve/", headers=headers, json={
        "resolution_code": "PERMANENT_FIX",
        "resolution_notes": "Increased connection pool size and patched query timeout settings."
    })

    if res.status_code != 200:
        print(f"   ✗ Resolve FAILED! {res.status_code}")
        print("   ", json.dumps(res.json(), indent=2)[:500])
        sys.exit(1)

    inc = res.json()["data"]
    print(f"   ✓ Resolved: State={inc['state']} | resolved_at={inc.get('resolved_at')}")

    # 5. Close (Manager confirms closure)
    print(f"\n5. Closing {inc_num} ...")
    res = requests.post(f"{BASE_URL}/incidents/{inc_id}/close/", headers=headers, json={})

    if res.status_code != 200:
        print(f"   ✗ Close FAILED! {res.status_code}")
        print("   ", json.dumps(res.json(), indent=2)[:500])
        sys.exit(1)

    inc = res.json()["data"]
    print(f"   ✓ Closed: State={inc['state']} | closed_at={inc.get('closed_at')}")

    # 6. Create another incident to promote to Problem
    print("\n6. Creating second Incident to promote to Problem ...")
    res = requests.post(f"{BASE_URL}/incidents/", headers=headers, json={
        "short_description": "Recurring DB timeouts — Root Cause Unknown",
        "description": "This is the 5th time this week. Needs root cause analysis.",
        "impact": "ENTERPRISE",
        "urgency": "HIGH",
        "category": "Database"
    })

    if res.status_code != 201:
        print(f"   ✗ Second incident creation FAILED! {res.status_code}")
        sys.exit(1)

    inc2 = res.json()["data"]
    print(f"   ✓ Created: {inc2['number']}")

    # 7. Promote to Problem
    print(f"\n7. Promoting {inc2['number']} to Problem ...")
    res = requests.post(f"{BASE_URL}/incidents/{inc2['id']}/promote-to-problem/", headers=headers)

    if res.status_code != 201:
        print(f"   ✗ Promote FAILED! {res.status_code}")
        print("   ", json.dumps(res.json(), indent=2)[:500])
        sys.exit(1)

    prob = res.json()["data"]
    print(f"   ✓ Problem Created: {prob['number']} | State={prob['state']}")

    # 8. Verify Change with atomic CHG number
    print("\n8. Creating a Change with atomic sequence number ...")
    res = requests.post(f"{BASE_URL}/changes/", headers=headers, json={
        "short_description": "Increase DB connection pool size",
        "description": "Change to increase max_connections from 100 to 500.",
        "type": "NORMAL",
        "risk_level": "LOW",
        "category": "Database",
        "justification": "Prevent future timeouts",
        "implementation_plan": "Run ALTER SYSTEM SET max_connections = 500",
        "rollback_plan": "ALTER SYSTEM SET max_connections = 100",
        "test_plan": "Monitor pg_stat_activity for 30 minutes post-change"
    })

    if res.status_code != 201:
        print(f"   ✗ Change creation FAILED! {res.status_code}")
        print("   ", json.dumps(res.json(), indent=2)[:500])
        sys.exit(1)

    chg = res.json()["data"]
    print(f"   ✓ Change Created: {chg['number']} | Type={chg['type']} | State={chg['state']}")
    assert chg['number'].startswith("CHG"), f"Expected CHG prefix, got: {chg['number']}"
    print(f"   ✓ Number format validated: {chg['number']}")

    print("\n" + "=" * 60)
    print("✅  ALL 8 E2E TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
