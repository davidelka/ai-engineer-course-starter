import re


def parse_vacation_policy(text):
    lines = [line for line in text.splitlines() if line.strip().startswith("-")]
    out = {}
    for line in lines:
        nums = re.findall(r"\d+", line)
        if "first year" in line:
            out["first_year_days"] = int(nums[0])
        elif "maximum" in line:
            out["yearly_increment"] = int(nums[0])
            out["max_days"] = int(nums[1])
        elif "carried over" in line:
            out["carryover_days"] = int(nums[0])
            out["carryover_expiry"] = re.search(r"expire on (.+?)\.", line).group(1)
        elif "in advance" in line:
            out["notice_weeks"] = int(nums[0])
        elif "shutdown" in line:
            out["shutdown_days"] = int(nums[0])
    return out
