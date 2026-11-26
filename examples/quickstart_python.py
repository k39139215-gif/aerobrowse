from aerobrowse import AeroBrowser

with AeroBrowser() as browser:
    result = browser.fetch("https://example.com")
    print(result)
