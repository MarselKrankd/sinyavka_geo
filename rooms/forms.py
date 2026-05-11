from django import forms

from .models import Map, Room

class RoomCreateForm(forms.ModelForm):
    map = forms.ModelChoiceField(queryset=Map.objects.all(), to_field_name='key', label='Карта', empty_label=None)

    class Meta:
        model = Room
        fields = ['name', 'map', 'is_private', 'max_players', 'rounds_total', 'round_duration_sec']
        labels = {
            'name': 'Название комнаты',
            'is_private': 'Приватная (только по ссылке)',
            'max_players': 'Макс. игроков',
            'rounds_total': 'Раундов',
            'round_duration_sec': 'Длительность раунда (сек)',
        }
        widgets = {
            'name': forms.TextInput(attrs={'maxlength': 80}),
            'max_players': forms.NumberInput(attrs={'min': 2, 'max': 12}),
            'rounds_total': forms.NumberInput(attrs={'min': 1, 'max': 10}),
            'round_duration_sec': forms.NumberInput(attrs={'min': 30, 'max': 300, 'step': 10}),
        }

    def clean_max_players(self):
        v = self.cleaned_data['max_players']
        if not 2 <= v <= 12:
            raise forms.ValidationError('Игроков должно быть от 2 до 12.')
        return v

    def clean_rounds_total(self):
        v = self.cleaned_data['rounds_total']
        if not 1 <= v <= 10:
            raise forms.ValidationError('Раундов должно быть от 1 до 10.')
        return v
