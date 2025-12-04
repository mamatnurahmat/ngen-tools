"""Teams notification module for sending webhook notifications."""
import json
from typing import Dict, Any, Optional

import requests

from .config import get_teams_webhook


def send_teams_notification(title: str, message: str, color: str = "0078D4", 
                            facts: Optional[Dict[str, str]] = None) -> bool:
    """Send notification to Microsoft Teams via webhook.
    
    Args:
        title: Notification title
        message: Notification message
        color: Theme color in hex (default: blue 0078D4)
        facts: Optional dictionary of facts to display
        
    Returns:
        bool: True if notification sent successfully, False otherwise
    """
    webhook_url = get_teams_webhook()
    
    if not webhook_url:
        # No webhook configured, skip silently
        return False
    
    # Build Teams message card
    card = {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "themeColor": color,
        "title": title,
        "text": message
    }
    
    # Add facts if provided
    if facts:
        card["sections"] = [{
            "facts": [{"name": k, "value": v} for k, v in facts.items()]
        }]
    
    try:
        response = requests.post(
            webhook_url,
            headers={"Content-Type": "application/json"},
            data=json.dumps(card),
            timeout=5
        )
        
        if response.status_code == 200:
            return True
        else:
            print(f"⚠️  Teams notification failed: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"⚠️  Teams notification failed: {str(e)}")
        return False


def notify_branch_created(repo: str, src_branch: str, dest_branch: str, 
                         branch_url: str, user: Optional[str] = None) -> None:
    """Send notification for branch creation.
    
    Args:
        repo: Repository name
        src_branch: Source branch name
        dest_branch: Destination branch name
        branch_url: Branch URL
        user: User who triggered the action
    """
    facts = {
        "Repository": repo,
        "Source Branch": src_branch,
        "New Branch": dest_branch,
        "Branch URL": branch_url
    }
    if user:
        facts["Triggered By"] = user
        
    send_teams_notification(
        title=f"🌿 Branch Created: {dest_branch}",
        message=f"New branch created in repository **{repo}**",
        color="28A745",  # Green
        facts=facts
    )


def notify_image_updated(repo: str, branch: str, yaml_path: str, 
                        image: str, commit: str, user: Optional[str] = None) -> None:
    """Send notification for image update.
    
    Args:
        repo: Repository name
        branch: Branch name
        yaml_path: YAML file path
        image: New image
        commit: Commit message
        user: User who triggered the action
    """
    facts = {
        "Repository": repo,
        "Branch": branch,
        "YAML File": yaml_path,
        "New Image": image,
        "Commit": commit
    }
    if user:
        facts["Triggered By"] = user

    send_teams_notification(
        title=f"🖼️ Image Updated: {image}",
        message=f"Container image updated in repository **{repo}**",
        color="0078D4",  # Blue
        facts=facts
    )


def notify_pr_created(repo: str, src_branch: str, dest_branch: str, 
                     pr_id: int, pr_url: str, user: Optional[str] = None) -> None:
    """Send notification for pull request creation.
    
    Args:
        repo: Repository name
        src_branch: Source branch name
        dest_branch: Destination branch name
        pr_id: Pull request ID
        pr_url: Pull request URL
        user: User who triggered the action
    """
    facts = {
        "Repository": repo,
        "Source": src_branch,
        "Destination": dest_branch,
        "PR ID": f"#{pr_id}",
        "PR URL": pr_url
    }
    if user:
        facts["Triggered By"] = user

    send_teams_notification(
        title=f"🔄 Pull Request Created: #{pr_id}",
        message=f"New pull request created in repository **{repo}**",
        color="6F42C1",  # Purple
        facts=facts
    )


def notify_pr_merged(repo: str, pr_id: str, src_branch: str, dest_branch: str,
                    merge_commit: str, user: Optional[str] = None) -> None:
    """Send notification for pull request merge.
    
    Args:
        repo: Repository name
        pr_id: Pull request ID
        src_branch: Source branch name
        dest_branch: Destination branch name
        merge_commit: Merge commit hash
        user: User who triggered the action
    """
    facts = {
        "Repository": repo,
        "PR ID": f"#{pr_id}",
        "Source": src_branch,
        "Destination": dest_branch,
        "Merge Commit": merge_commit
    }
    if user:
        facts["Triggered By"] = user

    send_teams_notification(
        title=f"✅ Pull Request Merged: #{pr_id}",
        message=f"Pull request merged in repository **{repo}**",
        color="28A745",  # Green
        facts=facts
    )
