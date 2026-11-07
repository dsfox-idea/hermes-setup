from copy import copy, deepcopy
import math

from mflux.models.common.schedulers.linear_scheduler import LinearScheduler


class LightningScheduler(LinearScheduler):
    def __init__(self, config):
        if config.num_inference_steps != 4 or config.guidance != 1.0:
            raise ValueError('The installed Lightning adapter requires 4 steps and guidance 1.0')
        local_config = copy(config)
        local_config.model_config = deepcopy(config.model_config)
        local_config.model_config.sigma_base_shift = math.log(3)
        local_config.model_config.sigma_max_shift = math.log(3)
        local_config.model_config.sigma_shift_terminal = None
        super().__init__(local_config)
