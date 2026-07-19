"""예산 초과 시 프로젝트 결제(billing)를 자동으로 비활성화하는 Cloud Function.

GCP 예산 알림이 Pub/Sub 로 보내는 메시지를 받아서, 실제 비용이 예산을 넘으면
프로젝트에서 결제 계정을 분리한다. 결제가 분리되면 과금이 멈추고(무료 초과 폭주 방지)
해당 프로젝트의 리소스(VM 등)도 정지된다.

주의: 이 함수가 발동하면 봇 VM 도 함께 정지된다. 다시 켜려면 결제를 재연결해야 한다.
"""

import base64
import json
import os

from googleapiclient import discovery

# 배포 시 --set-env-vars 로 주입 (예: GUARD_PROJECT_ID=my-study-bot)
PROJECT_ID = os.environ.get("GUARD_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")


def _project_name() -> str:
    if not PROJECT_ID:
        raise RuntimeError("GUARD_PROJECT_ID 환경변수가 설정되지 않았습니다.")
    return f"projects/{PROJECT_ID}"


def stop_billing(cloud_event) -> None:
    """Pub/Sub(Eventarc CloudEvent) 트리거 진입점."""
    encoded = cloud_event.data["message"]["data"]
    payload = json.loads(base64.b64decode(encoded).decode("utf-8"))

    cost = float(payload.get("costAmount", 0))
    budget = float(payload.get("budgetAmount", 0))
    print(f"예산 알림 수신: 비용={cost}, 예산={budget}")

    if cost <= budget:
        print("비용이 예산 이하 → 조치 없음.")
        return

    billing = discovery.build("cloudbilling", "v1", cache_discovery=False)
    projects = billing.projects()
    name = _project_name()

    info = projects.getBillingInfo(name=name).execute()
    if not info.get("billingEnabled"):
        print("결제가 이미 비활성화되어 있음 → 조치 없음.")
        return

    # billingAccountName 을 빈 문자열로 두면 프로젝트에서 결제 계정이 분리된다.
    res = projects.updateBillingInfo(
        name=name, body={"billingAccountName": ""}
    ).execute()
    print(f"⚠️ 결제 비활성화 완료: {json.dumps(res)}")
