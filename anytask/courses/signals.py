from django.dispatch import Signal


after_save = Signal(providing_args=["instance"])