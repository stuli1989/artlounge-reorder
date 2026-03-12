"""
HTTP client for Tally Prime's XML API.

Tally Prime exposes an HTTP server (default port 9000) that accepts
XML POST requests and returns XML responses.
"""
import re
import requests
from lxml import etree

# Tally responses can contain invalid XML control characters in two forms:
# 1. Raw bytes (0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F)
# 2. XML character references like &#4; or &#x4; that encode invalid chars
_INVALID_XML_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_INVALID_XML_CHAR_REFS = re.compile(r"&#x?[0-9a-fA-F]+;")


class TallyClient:
    def __init__(self, host="localhost", port=9000):
        self.base_url = f"http://{host}:{port}"

    @staticmethod
    def _sanitize_xml(raw: bytes) -> bytes:
        """Remove invalid XML control characters from Tally response."""
        text = raw.decode("utf-8", errors="replace")
        # Strip raw control characters
        cleaned = _INVALID_XML_CHARS.sub("", text)
        # Strip XML character references that encode invalid chars (e.g. &#4; &#x4;)
        def _replace_char_ref(match):
            ref = match.group(0)  # e.g. "&#4;" or "&#x1f;"
            try:
                if ref.startswith("&#x"):
                    code = int(ref[3:-1], 16)
                else:
                    code = int(ref[2:-1])
                # Keep valid XML chars: tab(9), newline(10), carriage return(13), and 0x20+
                if code in (9, 10, 13) or code >= 0x20:
                    return ref  # valid, keep it
                return ""  # invalid, strip it
            except ValueError:
                return ref  # not a number, keep as-is
        cleaned = _INVALID_XML_CHAR_REFS.sub(_replace_char_ref, cleaned)
        return cleaned.encode("utf-8")

    def send_request(self, xml_request: str, timeout=300) -> etree._Element:
        """POST XML to Tally and return parsed lxml Element."""
        raw = self.send_request_raw(xml_request, timeout=timeout)
        sanitized = self._sanitize_xml(raw)
        try:
            return etree.fromstring(sanitized)
        except etree.XMLSyntaxError as e:
            raise ValueError(f"Tally returned invalid XML: {e}")

    def send_request_raw(self, xml_request: str, timeout=300) -> bytes:
        """POST XML to Tally and return raw response bytes."""
        try:
            response = requests.post(
                self.base_url,
                data=xml_request.encode("utf-8"),
                headers={"Content-Type": "application/xml"},
                timeout=timeout,
            )
            response.raise_for_status()
            return response.content
        except requests.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Tally at {self.base_url}. "
                "Is Tally running with the HTTP server enabled?"
            )
        except requests.Timeout:
            raise ConnectionError(
                f"Tally request timed out after {timeout}s. "
                "Try a smaller date range or increase the timeout."
            )
        except requests.HTTPError as e:
            raise ConnectionError(f"Tally HTTP error: {e}")

    def test_connection(self) -> bool:
        """Test connection by requesting the list of companies."""
        test_xml = """<ENVELOPE>
  <HEADER>
    <VERSION>1</VERSION>
    <TALLYREQUEST>Export</TALLYREQUEST>
    <TYPE>Collection</TYPE>
    <ID>List of Companies</ID>
  </HEADER>
  <BODY>
    <DESC>
      <STATICVARIABLES>
        <SVEXPORTFORMAT>$$SysName:XML</SVEXPORTFORMAT>
      </STATICVARIABLES>
    </DESC>
  </BODY>
</ENVELOPE>"""
        try:
            root = self.send_request(test_xml, timeout=30)
            companies = root.findall(".//COMPANY")
            if not companies:
                # Try alternate path — Tally response structure can vary
                companies = root.findall(".//{*}COMPANY")
            if companies:
                print(f"Connected to Tally at {self.base_url}")
                print(f"Companies found: {len(companies)}")
                for c in companies:
                    name = c.findtext("NAME") or c.findtext("{*}NAME") or c.text or "(unknown)"
                    print(f"  - {name.strip()}")
                return True
            else:
                # Connection worked but no companies parsed — print raw for debugging
                print(f"Connected to Tally at {self.base_url}")
                print("Response received but no COMPANY elements found.")
                print("Raw response (first 500 chars):")
                print(etree.tostring(root, pretty_print=True).decode()[:500])
                return True
        except (ConnectionError, ValueError) as e:
            print(f"Connection failed: {e}")
            return False
