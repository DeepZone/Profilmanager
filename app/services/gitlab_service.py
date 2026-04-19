from urllib.parse import quote

import requests


class GitLabServiceError(Exception):
    pass


class GitLabService:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"PRIVATE-TOKEN": token}

    def _request(self, method, path, **kwargs):
        url = f"{self.base_url}/api/v4{path}"
        resp = requests.request(method, url, headers=self.headers, timeout=30, **kwargs)
        if resp.status_code >= 400:
            raise GitLabServiceError(
                f"GitLab API Fehler ({resp.status_code}): {resp.text[:500]}"
            )
        if resp.text:
            return resp.json()
        return {}

    def test_connection(self):
        return self._request("GET", "/user")

    def list_projects(self, search=None):
        params = {"membership": True, "per_page": 50}
        if search:
            params["search"] = search
        return self._request("GET", "/projects", params=params)

    def create_branch(self, project_id: int, branch_name: str, ref: str):
        return self._request(
            "POST",
            f"/projects/{project_id}/repository/branches",
            data={"branch": branch_name, "ref": ref},
        )

    def commit_file(self, project_id: int, branch: str, file_path: str, content: str, message: str):
        encoded = quote(file_path, safe="")
        return self._request(
            "POST",
            f"/projects/{project_id}/repository/files/{encoded}",
            data={
                "branch": branch,
                "content": content,
                "commit_message": message,
                "encoding": "base64",
            },
        )

    def update_file(self, project_id: int, branch: str, file_path: str, content: str, message: str):
        encoded = quote(file_path, safe="")
        return self._request(
            "PUT",
            f"/projects/{project_id}/repository/files/{encoded}",
            data={
                "branch": branch,
                "content": content,
                "commit_message": message,
                "encoding": "base64",
            },
        )

    def create_merge_request(
        self, project_id: int, source_branch: str, target_branch: str, title: str
    ):
        return self._request(
            "POST",
            f"/projects/{project_id}/merge_requests",
            data={
                "source_branch": source_branch,
                "target_branch": target_branch,
                "title": title,
            },
        )

    def list_merge_requests(self, project_id: int, state="all"):
        return self._request(
            "GET", f"/projects/{project_id}/merge_requests", params={"state": state}
        )

    def get_merge_request(self, project_id: int, mr_iid: int):
        return self._request("GET", f"/projects/{project_id}/merge_requests/{mr_iid}")

    def get_merge_request_changes(self, project_id: int, mr_iid: int):
        return self._request("GET", f"/projects/{project_id}/merge_requests/{mr_iid}/changes")

    def merge_request(self, project_id: int, mr_iid: int, squash=False):
        return self._request(
            "PUT",
            f"/projects/{project_id}/merge_requests/{mr_iid}/merge",
            data={"squash": squash},
        )
