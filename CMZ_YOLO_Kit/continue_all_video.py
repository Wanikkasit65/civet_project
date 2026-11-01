"""Resume an existing run, retaining per-file errors instead of aborting the batch.

Leaves all_video.py unchanged. All original error logging and exports are kept.
Missing footage is never converted into a behavior or marked complete.
"""
from pathlib import Path
import ast
import sys


def patched_source(source):
    tree = ast.parse(source)
    matches = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
            if isinstance(node.exc.func, ast.Name) and node.exc.func.id == 'RuntimeError':
                args = node.exc.args
                if args and isinstance(args[0], ast.BinOp):
                    text = ast.get_source_segment(source, node)
                    if "'Stopped on '" in text and "f['name']" in text:
                        matches.append(node)
    if len(matches) != 1:
        raise RuntimeError('Unexpected all_video.py version; no changes were made.')
    node = matches[0]
    lines = source.splitlines(keepends=True)
    lines[node.lineno-1:node.end_lineno] = [
        ' ' * node.col_offset + 'continue  # Keep recorded error and analyze remaining files.\n'
    ]
    result = ''.join(lines)
    compile(result, 'all_video.py (continue mode)', 'exec')
    return result


if __name__ == '__main__':
    root = Path(__file__).resolve().parent
    source_path = root / 'all_video.py'
    if len(sys.argv) != 2 or not (Path(sys.argv[1]) / 'config.json').is_file():
        raise SystemExit('Pass the existing run folder containing config.json.')
    source = patched_source(source_path.read_text(encoding='utf-8-sig'))
    print('Resume mode: retain per-file errors and continue other videos.', flush=True)
    exec(compile(source, str(source_path), 'exec'),
         {'__name__': '__main__', '__file__': str(source_path)})
