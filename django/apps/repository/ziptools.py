import json
import re
import io
from zipfile import ZipFile, BadZipFile
from PIL import Image

from django import forms
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

from repository.models import PackageVersion, Package

MAX_PACKAGE_SIZE = 1024 * 1024 * 50
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9\_]+$")
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class PackageVersionForm(forms.ModelForm):
    class Meta:
        model = PackageVersion
        fields = ["file"]

    def __init__(self, user, *args, **kwargs):
        super(PackageVersionForm, self).__init__(*args, **kwargs)
        self.user = user

    def validate_manifest(self, manifest):
        try:
            self.manifest = json.loads(manifest)
            if "name" not in self.manifest:
                raise ValidationError("manifest.json must contain a name")
            max_length = PackageVersion._meta.get_field("name").max_length
            if len(self.manifest["name"]) > max_length:
                raise ValidationError(f"Package name is too long, max: {max_length}")
            if not re.match(NAME_PATTERN, self.manifest["name"]):
                raise ValidationError(
                    f"Package names can only contain a-Z A-Z 0-9 and _ characers"
                )

            if "version_number" not in self.manifest:
                raise ValidationError("manifest.json must contain version")
            version = self.manifest["version_number"]
            max_length = PackageVersion._meta.get_field("version_number").max_length
            if len(version) > max_length:
                raise ValidationError(f"Package version number is too long, max: {max_length}")
            if not re.match(VERSION_PATTERN, self.manifest["version_number"]):
                raise ValidationError(
                    f"Version numbers must follow the Major.Minor.Patch format (e.g. 1.45.320)"
                )

            if Package.objects.filter(owner=self.user, versions__version_number=version).exists():
                raise ValidationError("Package of the same name and version already exists")

            max_length = PackageVersion._meta.get_field("website_url").max_length
            if len(self.manifest.get("website_url", "")) > max_length:
                raise ValidationError(f"Package website url is too long, max: {max_length}")
        except json.decoder.JSONDecodeError:
            raise ValidationError("Package manifest.json is in invalid format")

    def validate_icon(self, icon):
        try:
            self.icon = ContentFile(icon)
            image = Image.open(io.BytesIO(icon))
        except Exception:
            raise ValidationError("Unsupported or corrupt icon, must be png")

        if image.format != "PNG":
            raise ValidationError("Icon must be in png format")

        if not (image.size[0] == 512 and image.size[1] == 512):
            raise ValidationError("Invalid icon dimensions, must be 512x512")

    def clean_file(self):
        file = self.cleaned_data.get("file", None)
        if not file:
            raise ValidationError("Must upload a file")

        if file._size > MAX_PACKAGE_SIZE:
            raise ValidationError(f"Too large package, current maximum is {MAX_PACKAGE_SIZE} bytes")

        try:
            with ZipFile(file) as unzip:

                if unzip.testzip():
                    raise ValidationError("Corrupted zip file")

                try:
                    manifest = unzip.read("manifest.json")
                    self.validate_manifest(manifest)
                except KeyError:
                    raise ValidationError("Package is missing manifest.json")

                try:
                    icon = unzip.read("icon.png")
                    self.validate_icon(icon)
                except KeyError:
                    raise ValidationError("Package is missing icon.png")
        except (BadZipFile, NotImplementedError):
            raise ValidationError("Invalid zip file format")

        return file

    @transaction.atomic
    def save(self):
        self.instance.name = self.manifest["name"]
        self.instance.version_number = self.manifest["version_number"]
        self.instance.website_url = self.manifest["website_url"]
        self.instance.package = Package.objects.get_or_create(
            owner=self.user,
            name=self.instance.name,
        )[0]
        self.instance.icon.save("icon.png", self.icon)
        super(PackageVersionForm, self).save()
