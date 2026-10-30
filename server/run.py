# -*- coding: utf-8 -*-
"""run —— StackChan 后端便捷入口。

用法::

    py -3.12 server/run.py --serve --port 12800     # 起服务端
    py -3.12 server/run.py --text "你好呀"           # 离线跑一次 AI 闭环并打印摘要
    py -3.12 server/run.py --demo                   # 本地起服务端 + 设备模拟器，跑通完整闭环
    py -3.12 server/run.py --serve --provider stub  # 强制离线桩（不联网）

环境变量：MINIMAX_API_KEY（可选）/ MINIMAX_BASE_URL / STACKCHAN_PORT。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.bridge.ws_client import DeviceSimulator, WsLink, app_url  # noqa: E402
from server.stackchan_ai import protocol  # noqa: E402
from server.stackchan_ai.config import Config  # noqa: E402
from server.stackchan_ai.server import StackChanServer, _print_pipeline_summary  # noqa: E402


async def _demo(text: str, provider_name: str) -> int:
    """本地起服务端 + 设备模拟器 + App，跑通完整闭环。"""
    config = Config.from_env()
    config.host = "127.0.0.1"
    config.port = 0
    config.provider = provider_name
    server = StackChanServer(config, verbose=True)
    serve_task = asyncio.create_task(server.serve("127.0.0.1", 0))
    try:
        for _ in range(200):
            if server.bound_port:
                break
            await asyncio.sleep(0.02)
        if not server.bound_port:
            print("[demo] server did not start")
            return 1

        device = DeviceSimulator("127.0.0.1", server.bound_port)
        await device.connect()
        app = WsLink(app_url("127.0.0.1", server.bound_port, "demo-app"), "demo-app")
        await app.connect()
        await app.send_frame(protocol.TEXT_MESSAGE,
                             protocol.build_text_payload("68ee8fd73668", text))
        summary = await device.wait_for_dance(timeout=30.0)
        if summary is None:
            print("[demo] FAIL: device received no 0x14")
            return 1
        print("[demo] " + summary.describe())
        await app.close()
        await device.close()
        return 0
    finally:
        server.stop()
        serve_task.cancel()
        try:
            await serve_task
        except (asyncio.CancelledError, Exception):
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="server/run.py",
                                     description="StackChan cloud backend runner")
    parser.add_argument("--serve", action="store_true", help="start the WebSocket server")
    parser.add_argument("--demo", action="store_true",
                        help="run the full loop locally (server + device simulator)")
    parser.add_argument("--text", default=None,
                        help="run the AI pipeline offline once and print a summary")
    parser.add_argument("--provider", default=None,
                        choices=["auto", "minimax", "stub"], help="provider selection")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)

    config = Config.from_env()
    if args.provider:
        config.provider = args.provider
    if args.host:
        config.host = args.host
    if args.port:
        config.port = args.port

    if args.demo:
        return asyncio.run(_demo(args.text or "你好呀，今天过得怎么样？",
                                 args.provider or config.provider))

    if args.text is not None:
        server = StackChanServer(config)
        outcome = server.run_pipeline(args.text)
        _print_pipeline_summary(outcome)
        return 0

    if args.serve:
        try:
            asyncio.run(_serve(config))
        except KeyboardInterrupt:
            print("\n[server] bye")
        return 0

    parser.print_help()
    return 0


async def _serve(config: Config) -> None:
    server = StackChanServer(config)
    await server.serve()


if __name__ == "__main__":
    sys.exit(main())
