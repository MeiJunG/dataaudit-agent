"""Start a localhost-only candidate model without changing the active app/model processes."""
from __future__ import annotations

import argparse
import hashlib
import os
import socket
import subprocess
from pathlib import Path


def launch_arguments(server: Path, model: Path, alias: str, port: int, context: int) -> list[str]:
    if port in {8080, 7860} or not 1024 <= port <= 65535:
        raise ValueError('Use a dedicated unprivileged candidate port, not an app/baseline port.')
    if not 1024 <= context <= 8192:
        raise ValueError('Candidate context must be in 1024..8192 for this V100 trial.')
    return [str(server), '--model', str(model), '--alias', alias, '--host', '127.0.0.1',
            '--port', str(port), '--api-key', 'local', '--ctx-size', str(context), '--parallel', '1',
            '--threads', '8', '--threads-batch', '8', '--n-gpu-layers', '99', '--flash-attn', 'off',
            '--jinja', '--seed', '579', '--temp', '.7', '--top-p', '.8', '--top-k', '20', '--min-p', '0']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server',type=Path,required=True)
    parser.add_argument('--model',type=Path,required=True)
    parser.add_argument('--sha256',required=True)
    parser.add_argument('--gpu-uuid',required=True)
    parser.add_argument('--alias',default='qwen3-4b-instruct-2507')
    parser.add_argument('--port',type=int,default=8081)
    parser.add_argument('--context',type=int,default=4096)
    args=parser.parse_args()
    try:
        command=launch_arguments(args.server.resolve(),args.model.resolve(),args.alias,args.port,args.context)
        if not args.server.is_file() or not os.access(args.server,os.X_OK) or not args.model.is_file():
            raise ValueError('The model file and executable server must exist.')
        if len(args.sha256)!=64 or any(c not in '0123456789abcdef' for c in args.sha256):
            raise ValueError('Supply a lowercase hexadecimal SHA-256 digest.')
        digest=hashlib.sha256()
        with args.model.open('rb') as stream:
            for block in iter(lambda:stream.read(8*1024*1024),b''):
                digest.update(block)
        if digest.hexdigest()!=args.sha256:
            raise ValueError('Model checksum mismatch; candidate was not launched.')
        inventory=subprocess.check_output(['nvidia-smi','--query-gpu=uuid,memory.free','--format=csv,noheader,nounits'],text=True)
        available={row.split(',')[0].strip():int(row.split(',')[1].strip()) for row in inventory.splitlines()}
        if args.gpu_uuid not in available or available[args.gpu_uuid]<5120:
            raise ValueError('Select an available GPU UUID with at least 5120 MiB free for this trial.')
        with socket.socket() as check:
            check.bind(('127.0.0.1',args.port))
        env=dict(os.environ)
        env['CUDA_VISIBLE_DEVICES']=args.gpu_uuid
        print(f'Candidate only: alias={args.alias}, port={args.port}, GPU={args.gpu_uuid}',flush=True)
        os.execve(command[0],command,env)
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        parser.error(str(exc))


if __name__=='__main__':
    main()
