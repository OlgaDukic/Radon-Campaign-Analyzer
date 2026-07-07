from django import forms

from .models import Campaign, UploadedFile


class CampaignForm(forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "location", "description", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class UploadedFileForm(forms.ModelForm):
    class Meta:
        model = UploadedFile
        fields = ["file"]

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        allowed_extensions = (".csv", ".xls", ".xlsx")
        if not uploaded.name.lower().endswith(allowed_extensions):
            raise forms.ValidationError("Upload a CSV or Excel file.")
        return uploaded
