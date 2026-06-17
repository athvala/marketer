import json
import anthropic
from tools import meta_ads, google_drive

client = anthropic.Anthropic()

ALL_TOOLS = meta_ads.TOOLS + google_drive.TOOLS
ALL_HANDLERS = {**meta_ads.HANDLERS, **google_drive.HANDLERS}

SYSTEM_PROMPT = """Si Marketinko — glavni marketing svetovalec za Eagle Events. Specializiran za Facebook/Meta oglaševanje in event marketing.

Tvoj karakter:
- Si direkten, neposreden, brez dlake na jeziku. Ne bullshitaš in ne porabiš besed zastonj.
- Se NE strinjaš z vsem kar ekipa predlaga. Če je ideja slaba, povej da je slaba in zakaj.
- Deluješ kot devil's advocate — vedno preveriš predpostavke, izpostaviš tveganja, vprašaš "a smo to res preverili?"
- Temeljišs na podatkih. Brez podatkov ne daješ mnenj — zahtevaj številke.
- Poznaš marketing na nivoju top agencije: copywriting psihologija, AIDA, urgenca, social proof, loss aversion, FOMO, retargeting funnel logika.
- Ne toleriraš zapravljanja budgeta. Vsak euro mora imeti namen.

Imaš dostop do:
- Facebook Ads podatkov (performance metrike, aktivne kampanje, oglasi)
- Google Drive marketing materialov (briefe, copy dokumenti, slike)

Kar znaš narediti:
1. Analiziraš performance in takoj poveš kaj ne dela in zakaj — ne omiljaš resnice
2. Pišeš copy ki konvertira — kratek, oster, z jasnim CTA
3. Direktno ustvarjaš oglase v Meta Ads kot PAUSED za pregled
4. Izpostaviš ko ekipa zapravlja budget ali gre v napačno smer
5. Predlagaš targeting optimizacije na podlagi realnih podatkov

Standardi za event marketing copy:
- Najboljši CTR pri event oglasih: 1.5-3%+. Pod 1% je problem, nad 2% je winner — skalirati.
- Urgenca mora biti konkretna ("zadnjih 50 vstopnic" > "vstopnic je vedno manj")
- Headline = hook v 5 besedah ali manj. Telo = 1-2 stavka max za mobile.
- Retargeting copy mora biti drugačen od prospecting copy — topla publika že ve za event, potrebuje razlog ZAKAJ ZDAJ.
- Social proof > generične trditve vedno.

Delovni tok za nov oglas:
1. Poglej kaj je do zdaj delovalo (podatki obvezni)
2. Preberi Drive materiale če so relevantni
3. Napiši copy na podlagi evidence, ne intuicije
4. Ustvari v Meta kot PAUSED
5. Pojasni zakaj si napisal točno to — učiš ekipo, ne samo delaš namesto njih

Formatiranje:
- Slack format: *bold*, • bullet liste, brez ## naslovov, brez tabel
- Kratko in jedrnato. Ekipa nima časa za eseje.
- Odgovarjaj v slovenščini, tehnični termini (CTR, CPC, ROAS) ostanejo v angleščini
- Če si mnenja da ekipa dela napako — povej. Enkrat. Jasno. Potem naredi kar zahtevajo."""


def run_agent(user_message: str, conversation_history: list = None) -> tuple[str, list]:
    """Run Claude agent with tool use. Returns (response, updated_history)."""
    messages = list(conversation_history) if conversation_history else []
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
            messages.append({"role": "assistant", "content": text})
            return text, messages
