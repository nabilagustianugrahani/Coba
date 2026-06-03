import json
from pathlib import Path
import os
from datetime import datetime

class CookieManager:
    def __init__(self, cookies_dir="cookies"):
        self.base_cookies_path = Path(__file__).parent / cookies_dir
        self.profiles_path = self.base_cookies_path / "profiles"
        os.makedirs(self.profiles_path, exist_ok=True)

    def _get_profile_platform_path(self, platform, profile_name="default") -> Path:
        profile_dir = self.profiles_path / profile_name
        os.makedirs(profile_dir, exist_ok=True)
        return profile_dir / f"{platform}.json"

    def save(self, platform, profile_name="default") -> None:
        source_path = self.base_cookies_path / f"{platform}_cookies.json"
        destination_path = self._get_profile_platform_path(platform, profile_name)

        if not source_path.exists():
            print(f"Error: Source cookie file not found at {source_path}")
            return

        with open(source_path, 'r') as f_in:
            cookies_data = json.load(f_in)

        with open(destination_path, 'w') as f_out:
            json.dump(cookies_data, f_out, indent=4)
        print(f"Cookies for platform '{platform}' saved to profile '{profile_name}'.")

    def load(self, platform, profile_name="default") -> list:
        file_path = self._get_profile_platform_path(platform, profile_name)
        if not file_path.exists():
            print(f"Error: Cookie file not found for platform '{platform}' in profile '{profile_name}'.")
            return []
        with open(file_path, 'r') as f:
            return json.load(f)

    def delete(self, platform, profile_name="default") -> None:
        file_path = self._get_profile_platform_path(platform, profile_name)
        if file_path.exists():
            os.remove(file_path)
            print(f"Cookies for platform '{platform}' in profile '{profile_name}' deleted.")
        else:
            print(f"Error: Cookie file not found for platform '{platform}' in profile '{profile_name}'.")

    def list_profiles(self) -> list:
        profiles = [d.name for d in self.profiles_path.iterdir() if d.is_dir()]
        return profiles

    def export_firefox(self, platform, profile_name="default", output_path: str = None) -> None:
        cookies = self.load(platform, profile_name)
        if not cookies:
            print("No cookies to export.")
            return

        netscape_cookies = []
        for cookie in cookies:
            # Netscape format: domain TAB flag TAB path TAB secure TAB expiration TAB name TAB value
            domain = cookie.get('domain', '')
            path = cookie.get('path', '/')
            secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
            # httponly = 'TRUE' if cookie.get('httponly', False) else 'FALSE' # Not directly in Netscape
            expiration = int(cookie.get('expirationDate', 0)) # Assuming expirationDate is epoch time
            name = cookie.get('name', '')
            value = cookie.get('value', '')

            # Heuristic for flag: if domain starts with ., then it's a domain cookie, else it's a host cookie
            # Flag: A TRUE/FALSE value indicating if the cookie is accessible by all machines in a given domain.
            # TRUE for domain cookies (e.g., .example.com), FALSE for host-only cookies (e.g., www.example.com).
            flag = 'TRUE' if domain.startswith('.') else 'FALSE'

            netscape_cookies.append(
                f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}"
            )

        header = "# Netscape HTTP Cookie File\n# This is a generated file!  Do not edit.\n\n"

        output_content = header + "\n".join(netscape_cookies)

        if output_path:
            with open(output_path, 'w') as f:
                f.write(output_content)
            print(f"Cookies exported to Netscape format at {output_path}")
        else:
            print("Netscape format cookies:\n" + output_content)

    def import_from_browser(self, platform, browser_name="chromium") -> bool:
        print(f"To import cookies for '{platform}' from {browser_name}, please follow these manual steps:")
        print("1. Install a browser extension like 'EditThisCookie' (for Chrome/Chromium) or 'Cookie-Editor' (for Firefox).")
        print("2. Navigate to the website for which you want to export cookies (e.g., instagram.com for '{platform}').")
        print("3. Open the extension and find the option to export cookies. Look for JSON format export.")
        print("4. Save the exported JSON content to a file named '{platform}_cookies.json' in the 'browser/cookies' directory.")
        print(f"   Expected path: {self.base_cookies_path / f'{platform}_cookies.json'}")
        print("5. After saving the file, you can then use the 'save' method of CookieManager to move it to a profile.")
        return False

