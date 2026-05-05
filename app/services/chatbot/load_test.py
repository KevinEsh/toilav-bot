"""Load test for process_whatsapp_message.

Simulates N clients sending messages concurrently and reports latency stats.

Usage:
    uv run python load_test.py --clients 50
    uv run python load_test.py --clients 50 --mock-db
    uv run python load_test.py --clients 50 --real-llm
    uv run python load_test.py --clients 100 --message "Quiero hacer un pedido"
"""

import argparse
import asyncio
import os
import statistics
import sys
import time
from collections import Counter
from contextlib import ExitStack, asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))


def _make_payload(client_id: int, message: str) -> dict:
    wa_id = f"521550{client_id:07d}"
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": wa_id,
                                "phone_number_id": "987654321",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": f"Test User {client_id}"},
                                    "wa_id": wa_id,
                                }
                            ],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": f"wamid.test{client_id}_{int(time.time() * 1000)}",
                                    "timestamp": str(int(time.time())),
                                    "text": {"body": message},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def _make_mock_db_session():
    """Returns a get_session replacement that yields a fully mocked AsyncSession."""

    @asynccontextmanager
    async def mock_get_session():
        session = AsyncMock()

        # upsert_customer → returns a CustomerRow-like object
        customer_row = MagicMock()
        customer_row.c_id = 1
        customer_row.c_name = "Test User"
        customer_row.c_whatsapp_id = "52155000001"

        # store_cache / load_store → StoreRow-like
        store_row = MagicMock()
        store_row.s_id = 1
        store_row.s_name = "Test Store"
        store_row.s_description = "Tienda de prueba"
        store_row.s_rag_text = ""

        # products → empty dict
        # insert_message → returns m_id = 1
        # load_conversation → returns []
        # load_active_order → returns None
        # update_conversation, update_message_status → no-op

        def execute_side_effect(query, *args, **kwargs):
            result = MagicMock()
            mappings = MagicMock()
            mappings.first.return_value = {
                "c_id": 1,
                "c_name": "Test User",
                "c_whatsapp_id": "52155000001",
                "cv_history": None,
            }
            mappings.all.return_value = []
            result.mappings.return_value = mappings
            result.scalar.return_value = 1
            result.scalar_one_or_none.return_value = None
            return result

        session.execute = AsyncMock(side_effect=execute_side_effect)
        yield session

    return mock_get_session


async def _run_client(client_id: int, message: str) -> tuple[float, Exception | None]:
    payload = _make_payload(client_id, message)
    t_start = time.perf_counter()
    error = None
    try:
        from whatsapp_utils import process_whatsapp_message

        await process_whatsapp_message(payload)
    except Exception as e:
        error = e
    elapsed = time.perf_counter() - t_start
    return elapsed, error


def _percentile(data: list[float], pct: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = (len(sorted_data) - 1) * pct / 100
    lo, hi = int(idx), min(int(idx) + 1, len(sorted_data) - 1)
    return sorted_data[lo] + (sorted_data[hi] - sorted_data[lo]) * (idx - lo)


def _print_report(
    n_clients: int,
    wall_time: float,
    latencies: list[float],
    errors: list[Exception],
    mock_llm: bool,
    mock_db: bool,
) -> None:
    n_ok = n_clients - len(errors)
    pct_ok = 100.0 * n_ok / n_clients if n_clients else 0

    error_counts: Counter = Counter(type(e).__name__ for e in errors)

    bar = "━" * 52
    print(f"\n{bar}")
    print(f" LOAD TEST — {n_clients} clients │ mock-llm={mock_llm} │ mock-db={mock_db}")
    print(bar)
    print(f" Wall time    : {wall_time:>7.2f}s")
    print(f" Successes    : {n_ok:>3} / {n_clients}  ({pct_ok:.1f}%)")
    print(f" Errors       : {len(errors):>3} / {n_clients}")

    if latencies:
        print()
        print(" Latency (per client, seconds):")
        print(f"   min        : {min(latencies):>7.2f}s")
        print(f"   p50        : {_percentile(latencies, 50):>7.2f}s")
        print(f"   p95        : {_percentile(latencies, 95):>7.2f}s")
        print(f"   p99        : {_percentile(latencies, 99):>7.2f}s")
        print(f"   max        : {max(latencies):>7.2f}s")
        if len(latencies) > 1:
            print(f"   stdev      : {statistics.stdev(latencies):>7.2f}s")

    if error_counts:
        print()
        print(" Errors:")
        for name, count in error_counts.most_common():
            print(f"   {name}: {count}x")

    print(bar)


async def main(args: argparse.Namespace) -> None:
    mock_llm = not args.real_llm
    mock_db = args.mock_db

    patches = []

    if mock_llm:
        patches.append(
            patch(
                "whatsapp_utils.agent_generate_response",
                new=AsyncMock(return_value=("Tenemos almendras y pistaches 🌰", [])),
            )
        )

    if mock_db:
        mock_session_factory = _make_mock_db_session()
        patches.append(patch("whatsapp_utils.get_session", new=mock_session_factory))
        patches.append(patch("dbutils.get_session", new=mock_session_factory))

        # Also mock the TTL caches so they don't hit the DB
        from models import StoreRow

        fake_store = StoreRow(s_id=1, s_name="Test Store", s_description="")
        patches.append(
            patch(
                "whatsapp_utils.store_cache",
                new=MagicMock(aget=AsyncMock(return_value=fake_store)),
            )
        )
        patches.append(
            patch(
                "whatsapp_utils.products_cache",
                new=MagicMock(aget=AsyncMock(return_value={})),
            )
        )
        patches.append(
            patch(
                "whatsapp_utils.upsert_customer",
                new=AsyncMock(
                    return_value=MagicMock(c_id=1, c_name="Test", c_whatsapp_id="52155000001")
                ),
            )
        )
        patches.append(patch("whatsapp_utils.load_conversation", new=AsyncMock(return_value=[])))
        patches.append(patch("whatsapp_utils.load_active_order", new=AsyncMock(return_value=None)))
        patches.append(patch("whatsapp_utils.insert_message", new=AsyncMock(return_value=1)))
        patches.append(patch("whatsapp_utils.update_message_status", new=AsyncMock()))
        patches.append(patch("whatsapp_utils.update_conversation", new=AsyncMock()))

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)

        tasks = [
            asyncio.create_task(_run_client(i, args.message)) for i in range(args.clients)
        ]

        t_wall_start = time.perf_counter()
        results = await asyncio.gather(*tasks, return_exceptions=False)
        wall_time = time.perf_counter() - t_wall_start

    latencies = [lat for lat, _ in results]
    errors = [err for _, err in results if err is not None]

    _print_report(args.clients, wall_time, latencies, errors, mock_llm, mock_db)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load test: simulates N clients calling process_whatsapp_message concurrently.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--clients", type=int, default=10, metavar="N", help="Number of concurrent clients (default: 10)"
    )
    parser.add_argument(
        "--real-llm",
        action="store_true",
        help="Use real LLM API instead of mocking (slow, costs tokens)",
    )
    parser.add_argument(
        "--mock-db",
        action="store_true",
        help="Mock all DB queries (no PostgreSQL needed, tests pure logic)",
    )
    parser.add_argument(
        "--message",
        default="Hola, qué tienen disponible?",
        help='Message text each client sends (default: "Hola, qué tienen disponible?")',
    )
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
