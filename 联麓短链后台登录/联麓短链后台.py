import requests


URL = "https://www.shlianlu.com/doApi/manage/shortUrl/client/getAnalyse"

PARAMS = {
    "key": "48bc22b76c4e6b19b5b273cb40d606a3",
}

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Referer": "https://www.shlianlu.com/console/msgShort/generation",
    "version": "3.0.0",
    "cookie": "upms-server-session-id=adb5ea76-444e-4bc3-8360-e3be3ea3f288;"
}


def get_analyse(data: dict | None = None) -> dict:
    response = requests.post(
        URL,
        params=PARAMS,
        headers=HEADERS,
        data=data or {},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    form_data = {
        # Fill form fields here if the API requires them.
        # "pageIndex": 1,
        # "pageSize": 20,
    }

    result = get_analyse(form_data)
    print(result)
