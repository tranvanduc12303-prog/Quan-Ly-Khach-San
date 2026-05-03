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

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if not image:
            return image

        if hasattr(image, 'size') and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Ảnh quá lớn. Vui lòng chọn ảnh có dung lượng tối đa 5MB.')

        valid_mime_types = ['image/jpeg', 'image/png', 'image/gif']
        if hasattr(image, 'content_type') and image.content_type not in valid_mime_types:
            raise forms.ValidationError('Định dạng ảnh không hợp lệ. Vui lòng dùng JPG, PNG hoặc GIF.')

        return image
