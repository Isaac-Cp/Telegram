import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.lead_scoring import get_top_leads

async def main():
    print("Fetching the 20 highest-intent buyers detected in the last 7 days...")
    print("-" * 80)
    
    top_leads = await get_top_leads(limit=20, days=7)
    
    if not top_leads:
        print("No high-intent buyers found in the last 7 days.")
        return

    print(f"{'ID':<36} | {'Score':<5} | {'Temp':<10} | {'Message'}")
    print("-" * 80)
    
    for lead in top_leads:
        # Truncate message for display
        msg = lead.message_text.replace('\n', ' ')
        if len(msg) > 50:
            msg = msg[:47] + "..."
            
        print(f"{str(lead.id):<36} | {lead.lead_score:<5} | {lead.lead_temperature:<10} | {msg}")

if __name__ == "__main__":
    asyncio.run(main())
