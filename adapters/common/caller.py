"""Verified caller scope for agent receipts, never human/execution authority."""
import os
from pathlib import Path
from skip_core.common import digest, uid
from skip_core.errors import CoreError


def caller_scope(workspace, transport, receipt_scope=None):
    """Do not infer identity from an installed agent, cwd alone, or process ID.

    Unknown hosts retain connection-local receipts. A transport-owned persistent
    caller adapter can be added here without exposing identity fields to tools.
    """
    thread = os.environ.get('CODEX_THREAD_ID')
    if thread:
        from adapters.codex.provenance import current_user
        root = Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')/'sessions'
        try:
            current_user(root, thread, Path(workspace).resolve(strict=True))
        except (CoreError, OSError, ValueError, KeyError):
            pass
        else:
            return 'caller-v2-'+digest([transport, 'codex', str(root.resolve()), thread, str(Path(workspace).resolve())]), True
    if receipt_scope is not None:
        from skip_core.common import identifier
        identifier(receipt_scope)
        # Explicit client namespace is for deduplication only, not verified identity.
        return 'receipt-v2-'+digest([transport, str(Path(workspace).resolve()), receipt_scope]), False
    return 'connection-v2-'+uid(), False
