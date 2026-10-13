from django.db import migrations


def grant_head_office_to_existing_users(apps, schema_editor):
    """Preserve the previous behaviour for users that already exist.

    Branch access is deny-by-default, so without this every non-superuser would
    lose visibility of all branches after the upgrade. Granting the head office
    with descendants keeps their scope equivalent to "all branches" until an
    administrator narrows it.
    """
    Branch = apps.get_model("core", "Branch")
    User = apps.get_model("core", "User")
    BranchAccess = apps.get_model("core", "BranchAccess")

    head_office = Branch.objects.filter(is_head_office=True).first()
    if head_office is None:
        return

    for user in User.objects.filter(is_superuser=False).iterator():
        BranchAccess.objects.get_or_create(
            user=user,
            branch=head_office,
            defaults={"include_descendants": True},
        )


def remove_head_office_grants(apps, schema_editor):
    Branch = apps.get_model("core", "Branch")
    BranchAccess = apps.get_model("core", "BranchAccess")

    head_office = Branch.objects.filter(is_head_office=True).first()
    if head_office is None:
        return
    BranchAccess.objects.filter(branch=head_office, include_descendants=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0006_branchaccess"),
    ]

    operations = [
        migrations.RunPython(grant_head_office_to_existing_users, remove_head_office_grants),
    ]
