from io import BytesIO
from django.core.files.base import ContentFile
import matplotlib
# For non-GUI rendering
matplotlib.use('agg')

def save_plot(plt):
    f = BytesIO()
    plt.savefig(f, bbox_inches='tight')
    return ContentFile(f.getvalue())
