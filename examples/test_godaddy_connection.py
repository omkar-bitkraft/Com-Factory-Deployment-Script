"""
Quick test script to verify GoDaddy API client setup
Run this to test your GoDaddy OTE credentials

Usage:
    python test_godaddy_connection.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from src.api import GoDaddyClient, AuthenticationError, APIError
from src.utils.config import get_settings

console = Console()


def test_authentication():
    """Test if GoDaddy credentials are valid"""
    console.print("\n[bold cyan]Testing GoDaddy API Authentication...[/bold cyan]\n")
    
    try:
        # Load configuration
        settings = get_settings()
        
        # Display environment info
        info_table = Table(show_header=False, box=None)
        info_table.add_row("[cyan]Environment:[/cyan]", f"[yellow]{settings.godaddy_env}[/yellow]")
        info_table.add_row("[cyan]Base URL:[/cyan]", f"[blue]{settings.godaddy_base_url}[/blue]")
        info_table.add_row("[cyan]API Key:[/cyan]", f"[green]{settings.godaddy_api_key[:8]}...{settings.godaddy_api_key[-4:]}[/green]")
        
        console.print(info_table)
        console.print()
        
        # Initialize client
        client = GoDaddyClient()
        
        # Try to fetch domains (this will validate authentication)
        console.print("[yellow]→ Attempting to fetch account domains...[/yellow]")
        domains = client.get_domains()
        
        # Success!
        console.print(Panel(
            f"[bold green]✅ Authentication Successful![/bold green]\n\n"
            f"Found [cyan]{len(domains)}[/cyan] domain(s) in your account.",
            title="Connection Test",
            border_style="green"
        ))
        
        if domains:
            console.print("\n[bold]Your Domains:[/bold]")
            domain_table = Table(show_header=True, header_style="bold magenta")
            domain_table.add_column("Domain", style="cyan")
            domain_table.add_column("Status", style="green")
            
            for domain in domains[:5]:  # Show first 5
                domain_table.add_row(
                    domain.get("domain", "N/A"),
                    domain.get("status", "N/A")
                )
            
            console.print(domain_table)
        
        return True
        
    except FileNotFoundError as e:
        console.print(Panel(
            f"[bold red]❌ Configuration Error[/bold red]\n\n"
            f"{str(e)}\n\n"
            f"[yellow]→ Please copy .env.example to .env and add your credentials[/yellow]",
            title="Error",
            border_style="red"
        ))
        return False
        
    except AuthenticationError as e:
        console.print(Panel(
            f"[bold red]❌ Authentication Failed[/bold red]\n\n"
            f"{str(e)}\n\n"
            f"[yellow]→ Please check your GoDaddy API credentials in .env file[/yellow]",
            title="Error",
            border_style="red"
        ))
        return False
        
    except APIError as e:
        console.print(Panel(
            f"[bold red]❌ API Error[/bold red]\n\n"
            f"{str(e)}",
            title="Error",
            border_style="red"
        ))
        return False
        
    except Exception as e:
        console.print(Panel(
            f"[bold red]❌ Unexpected Error[/bold red]\n\n"
            f"{type(e).__name__}: {str(e)}",
            title="Error",
            border_style="red"
        ))
        return False


def test_domain_availability():
    """Test domain availability checking"""
    console.print("\n[bold cyan]Testing Domain Availability Check...[/bold cyan]\n")
    
    try:
        client = GoDaddyClient()
        
        test_domains = ["google.com", "thisisaprobablyavailabledomain12345.com"]
        
        results_table = Table(show_header=True, header_style="bold magenta")
        results_table.add_column("Domain", style="cyan")
        results_table.add_column("Available", style="yellow")
        results_table.add_column("Status", style="green")
        
        for domain in test_domains:
            console.print(f"[yellow]→ Checking {domain}...[/yellow]")
            result = client.check_availability(domain)
            
            available = result.get("available", False)
            status_icon = "✅" if available else "❌"
            status_text = "Available" if available else "Not Available"
            
            results_table.add_row(
                domain,
                status_icon,
                status_text
            )
        
        console.print()
        console.print(results_table)
        console.print()
        
        console.print(Panel(
            "[bold green]✅ Domain availability check working![/bold green]",
            border_style="green"
        ))
        
        return True
        
    except APIError as e:
        console.print(Panel(
            f"[bold red]❌ API Error[/bold red]\n\n"
            f"{str(e)}",
            title="Error",
            border_style="red"
        ))
        return False


def test_domain_suggestions():
    """Test domain suggestions"""
    console.print("\n[bold cyan]Testing Domain Suggestions...[/bold cyan]\n")
    
    try:
        client = GoDaddyClient()
        
        query = "coffee"
        console.print(f"[yellow]→ Getting suggestions for '{query}'...[/yellow]\n")
        
        suggestions = client.suggest_domains(query, limit=5)
        
        if suggestions:
            console.print("[bold]Suggested Domains:[/bold]")
            for i, domain in enumerate(suggestions, 1):
                console.print(f"  {i}. [cyan]{domain}[/cyan]")
            console.print()
        
        console.print(Panel(
            f"[bold green]✅ Found {len(suggestions)} suggestions![/bold green]",
            border_style="green"
        ))
        
        return True
        
    except APIError as e:
        console.print(Panel(
            f"[bold red]❌ API Error[/bold red]\n\n"
            f"{str(e)}",
            title="Error",
            border_style="red"
        ))
        return False


def main():
    """Run all tests"""
    console.print(Panel.fit(
        "[bold magenta]🚀 GoDaddy API Client Test Suite[/bold magenta]\n"
        "[dim]Testing connection and basic functionality[/dim]",
        border_style="magenta"
    ))
    
    # Test 1: Authentication
    auth_success = test_authentication()
    
    if not auth_success:
        console.print("\n[bold red]⚠️  Authentication failed. Fix credentials before proceeding.[/bold red]")
        return
    
    # Test 2: Domain Availability
    test_domain_availability()
    
    # Test 3: Domain Suggestions
    test_domain_suggestions()
    
    console.print("\n" + "="*60)
    console.print(Panel.fit(
        "[bold green]✅ All tests completed![/bold green]\n"
        "[dim]Your GoDaddy API client is ready to use.[/dim]",
        border_style="green"
    ))


if __name__ == "__main__":
    main()
