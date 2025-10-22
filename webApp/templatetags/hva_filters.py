"""
Custom template filters for HVA leaderboard display
"""
from django import template

register = template.Library()


@register.filter(name='format_xlm_threshold')
def format_xlm_threshold(value):
    """
    Format XLM threshold for display.
    
    Examples:
        10000 -> "10K XLM"
        100000 -> "100K XLM"
        1000000 -> "1.0M XLM"
        750000 -> "750K XLM"
    """
    try:
        num = float(value)
        
        if num >= 1000000:
            # Format as millions
            millions = num / 1000000
            if millions == int(millions):
                return f"{int(millions)}M XLM"
            return f"{millions:.1f}M XLM"
        elif num >= 1000:
            # Format as thousands
            thousands = num / 1000
            if thousands == int(thousands):
                return f"{int(thousands)}K XLM"
            return f"{thousands:.0f}K XLM"
        else:
            # Format as whole number
            return f"{int(num)} XLM"
    except (ValueError, TypeError):
        return str(value)
