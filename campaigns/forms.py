from django import forms

from .models import Campaign, CampaignResearchContext, UploadedFile


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


class Paper1AnalysisForm(forms.Form):
    timezone = forms.CharField(initial="Europe/Rome", max_length=80)
    resample = forms.CharField(initial="1H", max_length=20, label="Resample interval")
    gap_tolerance = forms.FloatField(initial=1.5, min_value=0.0001)
    rebuild_canonical = forms.BooleanField(
        initial=True,
        required=False,
        label="Rebuild canonical dataset",
    )
    run_sensitivity = forms.BooleanField(
        initial=True,
        required=False,
        label="Run regime threshold sensitivity",
    )
    export_excel = forms.BooleanField(
        initial=True,
        required=False,
        label="Export Excel report",
    )

    def clean_timezone(self):
        value = self.cleaned_data["timezone"].strip()
        if not value:
            raise forms.ValidationError("Timezone cannot be empty.")
        return value

    def clean_resample(self):
        value = self.cleaned_data["resample"].strip()
        if not value:
            raise forms.ValidationError("Resample interval cannot be empty.")
        return value


class ResearchContextForm(forms.ModelForm):
    class Meta:
        model = CampaignResearchContext
        exclude = ["campaign", "created_at", "updated_at"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 4}),
        }
