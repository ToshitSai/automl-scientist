import urllib.request
import urllib.error

url = "https://automl-scientist.vercel.app/api/health"
print("Checking:", url)
try:
    res = urllib.request.urlopen(url)
    print("SUCCESS STATUS:", res.status)
    print("BODY:", res.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTP ERROR CODE:", e.code)
    print("ERROR BODY:", e.read().decode('utf-8'))
except Exception as e:
    print("OTHER ERROR:", e)
