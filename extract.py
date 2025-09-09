import os
import requests, json, time
from dotenv import load_dotenv

load_dotenv()

RAWG_KEY = os.getenv("RAWG_API_KEY")
def fetch_rawg(api_key, limit=100000, page_size=500, out_file="games/all.json"):
    url = f"https://api.rawg.io/api/games?key={api_key}&page_size={page_size}"
    games, count = [], 0
    while url and count < limit:
        r = requests.get(url)
        if r.status_code != 200: 
            print(f"error: {r.status_code} - {r.text}")
            break
        data = r.json()
        for g in data.get("results", []):
            if count >= limit:
                break
            games.append({
                "id": g.get("id"),
                "title": g.get("name"),
                "genres": [x["name"] for x in g.get("genres", [])],
                "tags": [x["name"] for x in g.get("tags", [])],
                "images": {
                    "background": g.get("background_image"),
                    "screenshots": [s["image"] for s in g.get("short_screenshots", [])]
                }
            })
            count += 1
        url = data.get("next")
        time.sleep(1)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(games, f, indent=4, ensure_ascii=False)

def split_games_json(input_file="games/all.json", chunk_size=5000, output_dir="games"):
    with open(input_file, "r", encoding="utf-8") as f:
        games = json.load(f)
    
    total_games = len(games)
    num_chunks = (total_games + chunk_size - 1) // chunk_size
    
    for i in range(num_chunks):
        start_idx = i * chunk_size
        end_idx = min((i + 1) * chunk_size, total_games)
        chunk = games[start_idx:end_idx]
        
        output_file = os.path.join(output_dir, f"games_{i+1}.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(chunk, f, indent=4, ensure_ascii=False)
        
        print(f"Created {output_file} with {len(chunk)} games")

# fetch_rawg(RAWG_KEY)
split_games_json()