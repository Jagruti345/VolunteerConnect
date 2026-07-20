"""
Deployment verification.
After UserData runs (Apache install + S3 sync), poll the public IP until
the site actually responds with HTTP 200. This confirms deployment worked
end-to-end rather than just assuming the instance booted correctly.
"""

import time
import requests

from modules.logger import write_success, write_warn, write_error


def verify_deployment(public_ip, retries=15, delay=15):
    url = f"http://{public_ip}"
    write_warn(f"Verifying website is live at {url} ...")

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                write_success(f"Website is live: {url}")
                return True
        except requests.exceptions.RequestException:
            pass

        write_warn(f"Not ready yet (attempt {attempt}/{retries}), retrying in {delay}s...")
        time.sleep(delay)

    write_error(f"Website did not become reachable at {url} within the expected time.")
    write_error("The instance may still be running its boot script - check again shortly,")
    write_error("or SSH in and inspect /var/log/cloud-init-output.log.")
    return False
