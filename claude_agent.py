import json
import anthropic
from tools import meta_ads, google_drive

client = anthropic.Anthropic()

ALL_TOOLS = meta_ads.TOOLS + google_drive.TOOLS
ALL_HANDLERS = {**meta_ads.HANDLERS, **google_drive.HANDLERS}

SYSTEM_PROMPT = """Si Marketinko, AI asistent za Eagle Events marketing ekipo. Pomagaš optimizirati Facebook oglase.

Imaš dostop do:
- Facebook Ads podatkov (performance metrike, aktivne kampanje, oglasi)
- Google Drive marketing materialov (briefe, copy dokumenti, slike)

Tvoje naloge:
1. Analiziraš performance oglasom in identificiraš kaj deluje dobro/slabo
2. Pišeš nove oglase na podlagi materialov iz Google Drive (briefe, slike, copy dokumenti)
3. Direktno ustvarjaš oglase v Meta Ads — brez da mora človek karkoli narediti
4. Predlagaš targeting optimizacije na podlagi podatkov
5. Učiš se iz preteklih rezultatov in si zapomniš kaj je delovalo

Delovni tok za nov oglas:
1. Preberi relevantne materiale iz Drive (brief, obstoječ copy, slike)
2. Analiziraj kaj je do sedaj delovalo (performance podatki)
3. Napiši copy (naslov + tekst)
4. Ustvari creative v Meta Ads (create_ad_creative)
5. Ustvari oglas v ustreznem ad setu (create_ad) — privzeto PAUSED
6. Sporoči v Slack: oglas je pripravljen, link za pregled, predlog ali ga aktiviraš

POMEMBNO: Oglase vedno ustvarjaj kot PAUSED, razen če te ekipa eksplicitno prosi za ACTIVE. Vedno sporoči kaj si naredil in zakaj.

Pri analizi vedno:
- Primerjaj CTR z industrijskim povprečjem za event industrijo (~0.9-1.5%)
- Izpostavi oglase z nizkim CTR ampak visokim spend (neučinkoviti)
- Predlagaj konkretne spremembe copy-ja, ne samo splošne nasvete
- Odgovarjaj v slovenščini, razen ko gre za tehnične termine
- Formatiraj odgovore za Slack: uporabljaj *bold* za poudarke, • za sezname, brez ## naslovov in brez markdown tabel — namesto tabel uporabljaj preproste bullet liste
- Bodi jedrnat in konverzacijski, ne kot poročilo"""


def run_agent(user_message: str, conversation_history: list = None) -> str:
    """Run Claude agent with tool use. Returns final text response."""
    messages = conversation_history or []
    messages.append({"role": "user", "content": user_message})

    while True:
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=ALL_TOOLS,
            messages=messages,
        )

        # If Claude wants to use tools
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    try:
                        result = ALL_HANDLERS[tool_name](tool_input)
                        result_str = json.dumps(result, ensure_ascii=False, indent=2)
                    except Exception as e:
                        result_str = f"Napaka: {str(e)}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_str,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        else:
            # Final response
            text = next((b.text for b in response.content if hasattr(b, "text")), "")
            return text
