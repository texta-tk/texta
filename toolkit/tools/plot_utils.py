from io import BytesIO
from django.core.files.base import ContentFile
import matplotlib
# For non-GUI rendering
matplotlib.use('agg')

def save_plot(plt):
    f = BytesIO()
    plt.savefig(f)
    return ContentFile(f.getvalue())
