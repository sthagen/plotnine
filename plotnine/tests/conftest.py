import os
import warnings
import inspect
import shutil
import locale
import types
from copy import deepcopy

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.testing.compare import compare_images

from plotnine import ggplot, theme


TOLERANCE = 2           # Default tolerance for the tests
DPI = 72                # Default DPI for the tests

# This partial theme modifies all themes that are used in
# the test. It is limited to setting the size of the test
# images Should a test require a larger or smaller figure
# size, the dpi or aspect_ratio should be modified.
test_theme = theme(figure_size=(640/DPI, 480/DPI))

if not os.path.exists(os.path.join(
        os.path.dirname(__file__), 'baseline_images')):
    raise IOError(
        "The baseline image directory does not exist. "
        "This is most likely because the test data is not installed. "
        "You may need to install plotnine from source to get the "
        "test data.")


def raise_no_baseline_image(filename):
    raise Exception("Baseline image {} is missing".format(filename))


def ggplot_equals(gg, right):
    """
    Compare ggplot object to image determined by `right`

    Parameters
    ----------
    gg : ggplot
        ggplot object
    right : str | tuple
        Identifier. If a tuple, then first element is the
        identifier and the second element is a `dict`.
        The `dict` can have two keys
            - tol - tolerance for the image comparison, a float.
            - savefig_kwargs - Parameter used by MPL to save
                               the figure. This is a `dict`.

    The right looks like any one of the following::

       - 'identifier'
       - ('identifier', {'tol': 17})
       - ('identifier', {'tol': 17, 'savefig_kwargs': {'dpi': 80}})

    This function is meant to monkey patch ggplot.__eq__
    so that tests can use the `assert` statement.
    """
    _setup()
    if isinstance(right, (tuple, list)):
        name, params = right
        tol = params.get('tol', TOLERANCE)
        _savefig_kwargs = params.get('savefig_kwargs', {})
    else:
        name, tol = right, TOLERANCE
        _savefig_kwargs = {}

    savefig_kwargs = {'dpi': DPI}
    savefig_kwargs.update(_savefig_kwargs)

    gg += test_theme
    fig = gg.draw()
    test_file = inspect.stack()[1][1]
    filenames = make_test_image_filenames(name, test_file)

    # savefig ignores the figure face & edge colors
    facecolor = fig.get_facecolor()
    edgecolor = fig.get_edgecolor()
    if facecolor:
        savefig_kwargs['facecolor'] = facecolor
    if edgecolor:
        savefig_kwargs['edgecolor'] = edgecolor

    # Save the figure before testing whether the original image
    # actually exists. This makes creating new tests much easier,
    # as the result image can afterwards just be copied.
    fig.savefig(filenames.result, **savefig_kwargs)
    _teardown()
    if os.path.exists(filenames.baseline):
        shutil.copyfile(filenames.baseline, filenames.expected)
    else:
        # Putting the exception in short function makes for
        #  short pytest error messages
        raise_no_baseline_image(filenames.baseline)

    err = compare_images(filenames.expected, filenames.result,
                         tol, in_decorator=True)
    gg._err = err  # For the pytest error message
    return False if err else True


ggplot.__eq__ = ggplot_equals


def draw_test(self):
    """
    Try drawing the ggplot object

    Parameters
    ----------
    self : ggplot
        ggplot object

    This function is meant to monkey patch ggplot.draw_test
    so that tests can draw and not care about cleaning up
    the MPL figure.
    """
    try:
        figure = self.draw()
    except Exception as err:
        plt.close('all')
        raise err
    else:
        if figure:
            plt.close(figure)


ggplot.draw_test = draw_test


def build_test(self):
    """
    Try building the ggplot object

    Parameters
    ----------
    self : ggplot
        ggplot object

    This function is meant to monkey patch ggplot.build_test
    so that tests build.
    """
    self = deepcopy(self)
    self._build()
    return self


ggplot.build_test = build_test


def pytest_assertrepr_compare(op, left, right):
    if (isinstance(left, ggplot) and
            isinstance(right, (str, tuple)) and
            op == "=="):

        msg = ("images not close: {actual:s} vs. {expected:s} "
               "(RMS {rms:.2f})".format(**left._err))
        return [msg]


def make_test_image_filenames(name, test_file):
    """
    Create filenames for testing

    Parameters
    ----------
    name : str
        An identifier for the specific test. This will make-up
        part of the filenames.
    test_file : str
        Full path of the test file. This will determine the
        directory structure

    Returns
    -------
    out : types.SimpleNamespace
        Object with 3 attributes to store the generated filenames

            - result
            - baseline
            - expected

        `result`, is the filename for the image generated by the test.
        `baseline`, is the filename for the baseline image to which
        the result will be compared.
        `expected`, is the filename to the copy of the baseline that
        will be stored in the same directory as the result image.
        Creating a copy make comparison easier.
    """
    if '.png' not in name:
        name = name + '.png'

    basedir = os.path.abspath(os.path.dirname(test_file))
    basename = os.path.basename(test_file)
    subdir = os.path.splitext(basename)[0]

    baseline_dir = os.path.join(basedir, 'baseline_images', subdir)
    result_dir = os.path.abspath(os.path.join('result_images', subdir))

    if not os.path.exists(result_dir):
        os.makedirs(result_dir, exist_ok=True)

    base, ext = os.path.splitext(name)
    expected_name = '{}-{}{}'.format(base, 'expected', ext)

    filenames = types.SimpleNamespace(
        baseline=os.path.join(baseline_dir, name),
        result=os.path.join(result_dir, name),
        expected=os.path.join(result_dir, expected_name))
    return filenames


# This is called from the cleanup decorator
def _setup():
    # The baseline images are created in this locale, so we should use
    # it during all of the tests.
    try:
        locale.setlocale(locale.LC_ALL, str('en_US.UTF-8'))
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, str('English_United States.1252'))
        except locale.Error:
            warnings.warn(
                "Could not set locale to English/United States. "
                "Some date-related tests may fail")

    plt.switch_backend('Agg')  # use Agg backend for these test
    if mpl.get_backend().lower() != "agg":
        msg = ("Using a wrong matplotlib backend ({0}), "
               "which will not produce proper images")
        raise Exception(msg.format(mpl.get_backend()))

    # These settings *must* be hardcoded for running the comparison
    # tests
    mpl.rcdefaults()  # Start with all defaults
    mpl.rcParams['text.hinting'] = 'auto'
    mpl.rcParams['text.antialiased'] = True
    mpl.rcParams['text.hinting_factor'] = 8

    # make sure we don't carry over bad plots from former tests
    msg = ("no of open figs: {} -> find the last test with ' "
           "python tests.py -v' and add a '@cleanup' decorator.")
    assert len(plt.get_fignums()) == 0, msg.format(plt.get_fignums())


def _teardown():
    plt.close('all')
    # reset any warning filters set in tests
    warnings.resetwarnings()
