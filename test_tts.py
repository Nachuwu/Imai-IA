import asyncio
import edge_tts

async def main():
    voces = await edge_tts.list_voices()
    for v in voces:
        if "es-" in v["Locale"]:
            print(v["ShortName"], "-", v["Locale"])

asyncio.run(main())