#!/usr/bin/env python3
"""
Simple client for NexusScope investigations API.

Usage:
  python s3_api_client.py example.com
  python s3_api_client.py example.com --module domain --poll-interval 3
"""

import asyncio
import sys
import time
from typing import Any, Dict, Optional

import httpx


class InvestigationsClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 20.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def start_scan(self, target: str, module: str = "domain") -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/investigations"
        payload = {
            "target": target,
            "module": module,
            "options": {},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    async def get_scan_status(self, task_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/investigations/{task_id}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def scan_with_polling(
        self,
        target: str,
        module: str = "domain",
        poll_interval: float = 3.0,
        max_attempts: int = 120,
    ) -> Optional[Dict[str, Any]]:
        print(f"Starting scan for target={target}, module={module}")
        try:
            start = await self.start_scan(target=target, module=module)
        except httpx.HTTPError as exc:
            print(f"Failed to start scan: {exc}")
            return None

        task_id = start.get("task_id")
        if not task_id:
            print("Server did not return task_id")
            return None

        print(f"Task ID: {task_id}")
        for attempt in range(1, max_attempts + 1):
            try:
                status_payload = await self.get_scan_status(task_id)
            except httpx.HTTPError as exc:
                print(f"Status polling failed: {exc}")
                return None

            status = status_payload.get("status", "unknown")
            print(f"[{attempt}/{max_attempts}] status={status}")

            if status in {"completed", "failed"}:
                return status_payload

            await asyncio.sleep(poll_interval)

        print("Timed out waiting for completion")
        return None


def parse_args(argv: list[str]) -> Dict[str, Any]:
    target: Optional[str] = None
    module = "domain"
    poll_interval = 3.0

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--module" and i + 1 < len(argv):
            module = argv[i + 1]
            i += 2
            continue
        if arg == "--poll-interval" and i + 1 < len(argv):
            poll_interval = float(argv[i + 1])
            i += 2
            continue
        if not arg.startswith("--") and target is None:
            target = arg
        i += 1

    if not target:
        print("Usage: python s3_api_client.py <target> [--module domain] [--poll-interval 3]")
        sys.exit(1)

    return {"target": target, "module": module, "poll_interval": poll_interval}


async def main() -> None:
    args = parse_args(sys.argv[1:])
    client = InvestigationsClient()

    started_at = time.time()
    result = await client.scan_with_polling(
        target=args["target"],
        module=args["module"],
        poll_interval=args["poll_interval"],
    )
    elapsed = time.time() - started_at

    if not result:
        print("No result returned")
        sys.exit(1)

    print("\nFinal result:")
    print(result)
    print(f"Elapsed seconds: {elapsed:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
