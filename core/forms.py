from django import forms
from .models import Room

class RoomImageForm(forms.ModelForm):
    """Form để upload hình ảnh phòng"""
    class Meta:
        model = Room
        fields = ['image']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
                'id': 'imageInput'
            })
        }
        labels = {
            'image': 'Chọn hình ảnh phòng'
        }
