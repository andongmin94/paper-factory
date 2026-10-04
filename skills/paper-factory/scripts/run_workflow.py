"""Launch the verified bundled JSON controller without MCP or model calls."""
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
from probe import package_access, safe_error
from host_context import apply_prepared_host, consume_environment_argument

try:
    if not package_access()["verified"]:
        raise ValueError("Installed workflow resources differ from their inventory")
    environment_file, arguments = consume_environment_argument(sys.argv[1:])
    apply_prepared_host(environment_file)
    sys.argv[1:] = arguments
    sys.path.insert(0, str(ROOT / "src"))
    from paper_factory.cloud import _parser, main
    if _parser().parse_args().runtime_root is None:
        raise ValueError("Specify the exact --runtime-root returned by prepare_runtime")
except Exception as error:
    print(json.dumps({"error": safe_error(error), "instructions": "Use the verified package, prepare_host's private Python/environment_file, and prepare_runtime's runtime_root."}))
    raise SystemExit(1)

raise SystemExit(main())
