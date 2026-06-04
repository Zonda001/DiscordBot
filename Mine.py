import requests

API_KEY = '$2a$10$uvlv5Ul3DxJkWnkcg9cJy.vFGKS6zgvVsz/HFooFbrPgFrJj89F9i'
mod_name = 'storage-drawers'
mc_version = '1.20.1'
game_id = 432

search_url = f"https://api.curseforge.com/v1/mods/search?gameId={game_id}&slug={mod_name}"
headers = {"x-api-key": API_KEY}

search_response = requests.get(search_url, headers=headers).json()

if not search_response["data"]:
    raise Exception(f"No results found for {search_url}")

project_id = search_response["data"][0]["id"]
mod_full_name = search_response["data"][0]["name"]
print(f"Мод: {mod_full_name}, project_id: {project_id}")

files_url = f"https://api.curseforge.com/v1/projects/{project_id}/files"
files_response = requests.get(files_url, headers=headers).json()

files_found = False
for f in files_response["data"]:
    if mc_version in f["gameVersion"]:
        print(f"Є майн версія {mc_version}:")
        print(f" Назва файлу: {f['displayName']}")
        print(f" FileID: {f['id']}")
        files_found = True
        break

if not files_found:
    print(f"Ніхуя не знайшло")