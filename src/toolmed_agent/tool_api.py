import argparse
from pathlib import Path
from typing import Any, Dict, List

import uvicorn
from fastapi import Body, FastAPI

from .tool_registry import CalculationToolRegistry


def create_app(calc_tools_dir: str) -> FastAPI:
    registry = CalculationToolRegistry(calc_tools_dir=calc_tools_dir)
    app = FastAPI(title="MedAgent Calculation Tools")

    @app.get("/")
    def health() -> Dict[str, Any]:
        return {"status": "ok", "tool_count": len(registry.list_tools())}

    @app.get("/list")
    def list_tools() -> Dict[str, List[str]]:
        return {"tools": registry.list_tools()}

    @app.post("/tools/{calculator_id}/calculate")
    def calculate(calculator_id: str, relevant: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
        ret = registry.calculate(calculator_id, relevant)
        return {
            "calculator_id": ret.calculator_id,
            "tool_name": ret.tool_name,
            "result": ret.result,
            "error": ret.error,
        }

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run API server for generated calculation tools")
    parser.add_argument(
        "--calc-tools-dir",
        "--calc_tools_dir",
        dest="calc_tools_dir",
        default=str(Path.cwd() / "artifacts" / "calculators" / "gpt_5_5"),
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="bind address (default: loopback only; no authentication is provided)",
    )
    parser.add_argument("--port", type=int, default=8091)
    args = parser.parse_args()

    app = create_app(calc_tools_dir=args.calc_tools_dir)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
