from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import numpy as np
import pandas as pd

from ..utils import suppress
from ..utils.doctools import document
from ..utils.exceptions import PlotnineError
from .stat import stat


@document
class stat_function(stat):
    """
    Superimpose a function onto a plot

    {usage}

    Parameters
    ----------
    {common_parameters}

    {aesthetics}
    """
    DEFAULT_PARAMS = {'geom': 'path', 'position': 'identity',
                      'fun': None, 'n': 101, 'args': None,
                      'xlim': None}

    DEFAULT_AES = {'y': '..y..'}
    CREATES = {'y'}

    @classmethod
    def compute_group(cls, data, scales, **params):
        fun = params['fun']
        n = params['n']
        args = params['args']
        xlim = params['xlim']

        try:
            range_x = xlim or scales.x.dimension((0, 0))
        except AttributeError:
            raise PlotnineError(
                "Missing 'x' aesthetic and 'xlim' is {}".format(xlim))

        if not hasattr(fun, '__call__'):
            raise PlotnineError(
                "stat_function requires parameter 'fun' to be " +
                "a function or any other callable object")

        old_fun = fun
        if isinstance(args, (list, tuple)):
            def fun(x):
                return old_fun(x, *args)
        elif isinstance(args, dict):
            def fun(x):
                return old_fun(x, **args)
        elif args is not None:
            def fun(x):
                return old_fun(x, args)
        else:
            def fun(x):
                return old_fun(x)

        x = np.linspace(range_x[0], range_x[1], n)

        # continuous scale
        with suppress(AttributeError):
            x = scales.x.trans.inverse(x)

        # We know these can handle array-likes
        if isinstance(old_fun, (np.ufunc, np.vectorize)):
            y = fun(x)
        else:
            y = [fun(val) for val in x]

        new_data = pd.DataFrame({'x': x, 'y': y})
        return new_data
