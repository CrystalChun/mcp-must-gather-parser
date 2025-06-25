#!/usr/bin/env python3
"""
CLI interface for OpenShift Must-Gather MCP Server
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import click
import structlog
from rich.console import Console
from rich.table import Table
from rich.json import JSON
from rich.panel import Panel

from .config import MCPConfig
from .main import OpenShiftMustGatherMCPServer
from .tools import MustGatherTools
from .resources import MustGatherResources

console = Console()
logger = structlog.get_logger(__name__)


@click.group()
@click.option('--config-file', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--log-level', '-l', default='INFO', help='Log level (DEBUG, INFO, WARNING, ERROR)')
@click.option('--storage-dir', '-s', type=click.Path(), help='Storage directory for parsed data')
@click.pass_context
def cli(ctx, config_file, log_level, storage_dir):
    """OpenShift Must-Gather MCP Server CLI"""
    ctx.ensure_object(dict)
    
    # Setup configuration
    config = MCPConfig.from_env()
    if log_level:
        config.log_level = log_level
    if storage_dir:
        config.storage_dir = Path(storage_dir)
    
    ctx.obj['config'] = config
    
    # Setup logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer() if config.structured_logging 
            else structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog, config.log_level.upper(), structlog.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@cli.command()
@click.pass_context
async def server(ctx):
    """Start the MCP server"""
    config = ctx.obj['config']
    console.print(Panel(f"Starting OpenShift Must-Gather MCP Server", style="bold green"))
    console.print(f"Server: {config.server_name} v{config.server_version}")
    console.print(f"Storage: {config.storage_dir}")
    console.print(f"Log Level: {config.log_level}")
    
    server = OpenShiftMustGatherMCPServer(config)
    try:
        await server.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Server stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Server error: {e}[/red]")
        raise


@cli.command()
@click.argument('archive_path', type=click.Path(exists=True))
@click.option('--extract-logs/--no-extract-logs', default=False, help='Extract pod logs')
@click.option('--output', '-o', type=click.Choice(['json', 'table']), default='table', help='Output format')
@click.pass_context
async def parse(ctx, archive_path, extract_logs, output):
    """Parse a must-gather archive"""
    config = ctx.obj['config']
    console.print(f"[blue]Parsing must-gather archive:[/blue] {archive_path}")
    
    tools = MustGatherTools(config)
    await tools.initialize()
    
    try:
        # Parse the archive
        result = await tools.call_tool('parse_must_gather', {
            'file_path': archive_path,
            'extract_logs': extract_logs
        })
        
        if output == 'json':
            for content in result:
                if hasattr(content, 'text'):
                    try:
                        # Try to extract JSON from the text
                        lines = content.text.split('\n')
                        for line in lines:
                            if line.strip().startswith('{'):
                                data = json.loads(line)
                                console.print(JSON.from_data(data))
                                break
                    except:
                        console.print(content.text)
                else:
                    console.print(str(content))
        else:
            for content in result:
                if hasattr(content, 'text'):
                    console.print(content.text)
                else:
                    console.print(str(content))
                    
    except Exception as e:
        console.print(f"[red]Error parsing archive: {e}[/red]")
        raise


@cli.command()
@click.argument('must_gather_id')
@click.option('--degraded-only/--all', default=False, help='Show only degraded components')
@click.option('--output', '-o', type=click.Choice(['json', 'table']), default='table', help='Output format')
@click.pass_context
async def analyze_cluster(ctx, must_gather_id, degraded_only, output):
    """Analyze cluster health"""
    config = ctx.obj['config']
    console.print(f"[blue]Analyzing cluster health for:[/blue] {must_gather_id}")
    
    tools = MustGatherTools(config)
    await tools.initialize()
    
    try:
        result = await tools.call_tool('analyze_cluster_health', {
            'must_gather_id': must_gather_id,
            'include_degraded_only': degraded_only
        })
        
        for content in result:
            if hasattr(content, 'text'):
                if output == 'json':
                    try:
                        data = json.loads(content.text.split(':\n\n', 1)[1])
                        console.print(JSON.from_data(data))
                    except:
                        console.print(content.text)
                else:
                    console.print(content.text)
            else:
                console.print(str(content))
                
    except Exception as e:
        console.print(f"[red]Error analyzing cluster: {e}[/red]")
        raise


@cli.command()
@click.argument('must_gather_id')
@click.option('--node-name', '-n', help='Specific node to analyze')
@click.option('--output', '-o', type=click.Choice(['json', 'table']), default='table', help='Output format')
@click.pass_context
async def analyze_nodes(ctx, must_gather_id, node_name, output):
    """Analyze node issues"""
    config = ctx.obj['config']
    console.print(f"[blue]Analyzing node issues for:[/blue] {must_gather_id}")
    if node_name:
        console.print(f"[blue]Specific node:[/blue] {node_name}")
    
    tools = MustGatherTools(config)
    await tools.initialize()
    
    try:
        result = await tools.call_tool('analyze_node_issues', {
            'must_gather_id': must_gather_id,
            'node_name': node_name
        })
        
        for content in result:
            if hasattr(content, 'text'):
                if output == 'json':
                    try:
                        data = json.loads(content.text.split(':\n\n', 1)[1])
                        console.print(JSON.from_data(data))
                    except:
                        console.print(content.text)
                else:
                    console.print(content.text)
            else:
                console.print(str(content))
                
    except Exception as e:
        console.print(f"[red]Error analyzing nodes: {e}[/red]")
        raise


@cli.command()
@click.argument('must_gather_id')
@click.option('--namespace', '-n', help='Specific namespace to analyze')
@click.option('--include-logs/--no-include-logs', default=False, help='Include pod logs in analysis')
@click.option('--output', '-o', type=click.Choice(['json', 'table']), default='table', help='Output format')
@click.pass_context
async def analyze_pods(ctx, must_gather_id, namespace, include_logs, output):
    """Analyze pod failures"""
    config = ctx.obj['config']
    console.print(f"[blue]Analyzing pod failures for:[/blue] {must_gather_id}")
    if namespace:
        console.print(f"[blue]Namespace:[/blue] {namespace}")
    
    tools = MustGatherTools(config)
    await tools.initialize()
    
    try:
        result = await tools.call_tool('analyze_pod_failures', {
            'must_gather_id': must_gather_id,
            'namespace': namespace,
            'include_logs': include_logs
        })
        
        for content in result:
            if hasattr(content, 'text'):
                if output == 'json':
                    try:
                        data = json.loads(content.text.split(':\n\n', 1)[1])
                        console.print(JSON.from_data(data))
                    except:
                        console.print(content.text)
                else:
                    console.print(content.text)
            else:
                console.print(str(content))
                
    except Exception as e:
        console.print(f"[red]Error analyzing pods: {e}[/red]")
        raise


@cli.command()
@click.pass_context
def list_parsed(ctx):
    """List all parsed must-gather data"""
    config = ctx.obj['config']
    
    async def _list():
        resources = MustGatherResources(config)
        await resources.initialize()
        parsed_ids = await resources.list_parsed_data()
        
        if not parsed_ids:
            console.print("[yellow]No parsed must-gather data found[/yellow]")
            return
        
        table = Table(title="Parsed Must-Gather Data")
        table.add_column("Must-Gather ID", style="cyan")
        table.add_column("Status", style="green")
        
        for must_gather_id in parsed_ids:
            table.add_row(must_gather_id, "Parsed")
        
        console.print(table)
    
    asyncio.run(_list())


@cli.command()
@click.argument('must_gather_id')
@click.pass_context
def remove_parsed(ctx, must_gather_id):
    """Remove parsed must-gather data"""
    config = ctx.obj['config']
    
    async def _remove():
        resources = MustGatherResources(config)
        await resources.initialize()
        await resources.remove_parsed_data(must_gather_id)
        console.print(f"[green]Removed parsed data for:[/green] {must_gather_id}")
    
    asyncio.run(_remove())


@cli.command()
@click.pass_context
def list_resources(ctx):
    """List available MCP resources"""
    config = ctx.obj['config']
    
    async def _list():
        resources = MustGatherResources(config)
        await resources.initialize()
        resource_list = await resources.list_resources()
        
        if not resource_list:
            console.print("[yellow]No MCP resources available[/yellow]")
            return
        
        table = Table(title="Available MCP Resources")
        table.add_column("URI", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Description", style="white")
        table.add_column("MIME Type", style="yellow")
        
        for resource in resource_list:
            table.add_row(
                resource.uri,
                resource.name,
                resource.description,
                resource.mimeType
            )
        
        console.print(table)
    
    asyncio.run(_list())


@cli.command()
@click.pass_context
def list_tools(ctx):
    """List available MCP tools"""
    config = ctx.obj['config']
    
    async def _list():
        tools = MustGatherTools(config)
        await tools.initialize()
        tool_list = await tools.list_tools()
        
        table = Table(title="Available MCP Tools")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        
        for tool in tool_list:
            table.add_row(tool.name, tool.description)
        
        console.print(table)
    
    asyncio.run(_list())


def main():
    """Main entry point for CLI"""
    # Handle async commands
    commands_to_wrap = ['server', 'parse', 'analyze_cluster', 'analyze_nodes', 'analyze_pods']
    
    for cmd_name in commands_to_wrap:
        cmd = cli.commands.get(cmd_name)
        if cmd and asyncio.iscoroutinefunction(cmd.callback):
            original_callback = cmd.callback
            def make_sync_wrapper(async_func):
                def sync_wrapper(*args, **kwargs):
                    return asyncio.run(async_func(*args, **kwargs))
                return sync_wrapper
            cmd.callback = make_sync_wrapper(original_callback)
    
    cli()


if __name__ == '__main__':
    main() 