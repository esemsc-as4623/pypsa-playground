# pyoscomp/runners/pypsa.py

"""
Executes the PyPSA model from a ScenarioData object.

Uses PyPSAInputTranslator to build the network and PyPSA's modern
optimize() API for the linear programme.
"""

import logging
import pypsa

from ..interfaces.containers import ScenarioData
from ..translation.pypsa_translator import PyPSAInputTranslator, PyPSAOutputTranslator

logger = logging.getLogger(__name__)


class PyPSARunner:
    """
    Run a PyPSA capacity-expansion optimisation from a ScenarioData object.

    Parameters
    ----------
    scenario_data : ScenarioData
        Validated scenario data to optimise.
    solver_name : str, optional
        LP solver passed to ``network.optimize()`` (default: ``'highs'``).

    Examples
    --------
    >>> runner = PyPSARunner(scenario_data)
    >>> network = runner.run()
    >>> results = runner.get_results()
    """

    def __init__(self, scenario_data: ScenarioData, solver_name: str = "highs"):
        self.scenario_data = scenario_data
        self.solver_name = solver_name
        self.network: pypsa.Network | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(self) -> pypsa.Network:
        """
        Translate ScenarioData into a PyPSA Network without optimising.

        Returns
        -------
        pypsa.Network
            Fully configured network (not yet optimised).
        """
        translator = PyPSAInputTranslator(self.scenario_data)
        self.network = translator.translate()
        return self.network

    def run(self, **optimize_kwargs) -> pypsa.Network:
        """
        Build (if needed) and optimise the network.

        Parameters
        ----------
        **optimize_kwargs
            Additional keyword arguments forwarded to
            ``network.optimize()``.

        Returns
        -------
        pypsa.Network
            Solved network.

        Raises
        ------
        RuntimeError
            If the solver reports infeasibility or an error status.
        """
        if self.network is None:
            self.build()

        years = sorted(self.scenario_data.sets.years)
        multi = len(years) > 1

        logger.info(
            "Running PyPSA: %d year(s), solver=%s, multi=%s",
            len(years), self.solver_name, multi,
        )

        self.network.optimize(
            solver_name=self.solver_name,
            multi_investment_periods=multi,
            **optimize_kwargs,
        )

        status = getattr(self.network, "status", None)
        if status not in (None, "ok", "optimal", "warning:suboptimal"):
            raise RuntimeError(
                f"PyPSA optimisation finished with status '{status}'. "
                "Check solver output for details."
            )

        return self.network

    def get_results(self):
        """
        Extract harmonised ModelResults from the solved network.

        Returns
        -------
        ModelResults

        Raises
        ------
        RuntimeError
            If ``run()`` has not been called yet.
        """
        if self.network is None:
            raise RuntimeError(
                "No network available. Call run() before get_results()."
            )
        return PyPSAOutputTranslator(self.network).translate()
