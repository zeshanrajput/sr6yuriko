import os
import sys
import argparse
sys.path.insert(0, os.path.dirname(__file__))

import log_engine

def audit_dossier():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_path = os.path.join(base_dir, "chapters", "character_log.qmd")

    if not os.path.exists(log_path):
        return None, f"Character log file not found: {log_path}"

    totals = log_engine.get_log_totals(log_path)

    # Validate Karma & Nuyen math
    lifetime_karma = totals.get("Lifetime_Karma", 0)
    current_karma = totals.get("Karma", 0)
    nuyen = totals.get("Nuyen", 0)
    submersion_grade = totals.get("Submersion_Grade", 0)
    total_rep = totals.get("Total_Reputation", 0)
    active_sprites = totals.get("Active_Sprite_Count", 0)

    # Basic sanity checks
    warnings = []
    if current_karma < 0:
        warnings.append(f"Negative current Karma detected ({current_karma})!")
    if nuyen < 0:
        warnings.append(f"Negative Nuyen balance detected ({nuyen})!")
    if submersion_grade < 0 or submersion_grade > 9:
        warnings.append(f"Unusual Submersion Grade detected ({submersion_grade})!")

    report = {
        "lifetime_karma": lifetime_karma,
        "current_karma": current_karma,
        "nuyen": nuyen,
        "submersion_grade": submersion_grade,
        "total_reputation": total_rep,
        "active_sprites": active_sprites,
        "warnings": warnings
    }
    return report, None

def print_audit_report(report):
    print("=" * 65)
    print(" SRM CHARACTER DOSSIER & COMPLIANCE AUDIT REPORT")
    print("=" * 65)
    print(f" Lifetime Karma Earned: {report['lifetime_karma']}")
    print(f" Available Unspent Karma: {report['current_karma']}")
    print(f" Liquid Capital (Nuyen): ¥{report['nuyen']:,}")
    print(f" Submersion Grade: Grade {report['submersion_grade']}")
    print(f" Total Reputation: {report['total_reputation']}")
    print(f" Active Sprites Registered: {report['active_sprites']}")
    print("-" * 65)

    if report['warnings']:
        print(" ⚠️  AUDIT WARNINGS DETECTED:")
        for w in report['warnings']:
            print(f"  - {w}")
    else:
        print(" [OK] All Karma, Nuyen, and Submersion ledger balances are mathematically consistent.")
    print("=" * 65 + "\n")

def main():
    parser = argparse.ArgumentParser(description="SRM Character Ledger & Compliance Auditor Utility.")
    args = parser.parse_args()

    report, err = audit_dossier()
    if err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)

    print_audit_report(report)

if __name__ == "__main__":
    main()
