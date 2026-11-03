import re


def parse_vacation_policy(text):
    out = dict.fromkeys(["first_year_days", "yearly_increment", "max_days", "carryover_days",
                         "carryover_expiry", "notice_weeks", "shutdown_days"])
    for line in text.splitlines():
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
            out["notice_weeks"] = int(re.search(r"at least (\d+) weeks", line).group(1))
        elif "shutdown" in line:
            out["shutdown_days"] = int(nums[0])
    return out
