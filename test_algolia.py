import urllib.request
import re

url = 'https://www.deeplearning.ai/courses/'
try:
    with urllib.request.urlopen(url) as response:
        html = response.read().decode('utf-8')
        
        # Look for appId and apiKey
        # Search for any string that looks like an Algolia API key (usually 32 hex chars)
        matches = re.findall(r'[a-f0-9]{32}', html)
        print('Possible API Keys (32 hex):', list(set(matches)))
        
        # Search for app id which is usually 10 uppercase/lowercase letters/numbers
        matches = re.findall(r'\"([A-Z0-9]{10})\"', html, re.I)
        print('Possible App IDs (10 chars):', list(set(matches)))

        import json
        next_data = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
        if next_data:
            print("Found __NEXT_DATA__ length:", len(next_data.group(1)))
            data = json.loads(next_data.group(1))
            # recursive search for algolia
            def find_algolia(d):
                if isinstance(d, dict):
                    for k, v in d.items():
                        if 'algolia' in k.lower():
                            print('Found algolia key:', k, v)
                        find_algolia(v)
                elif isinstance(d, list):
                    for item in d:
                        find_algolia(item)
            find_algolia(data)
except Exception as e:
    print('Failed:', e)
