from tqdm import tqdm
import metrics.helper as utils
import numpy as np


def compute_empirical(step, layers, load_kwargs, empirical):
    weights = utils.load_features(steps=[str(step)], suffix="weight", **load_kwargs,)
    biases = utils.load_features(steps=[str(step)], suffix="bias", **load_kwargs,)
    W_in = weights[layers[0]][f"step_{step}"] ** 2
    b_in = biases[layers[0]][f"step_{step}"] ** 2
    for layer in layers[1:]:
        W_out = weights[layer][f"step_{step}"] ** 2
        b_out = biases[layer][f"step_{step}"] ** 2
        empirical[layer][step] = utils.out_synapses(W_out) - utils.in_synapses(
            W_in, b_in
        )
        W_in = W_out
        b_in = b_out


def compute_theoretical(
    step, layers, load_kwargs, theoretical, i, step_0, lr, wd, W_0, b_0,
):
    t = lr * step
    if i > 0:
        weight_buffers = utils.load_features(
            steps=[str(step)], suffix="weight.integral_buffer", **load_kwargs,
        )
        bias_buffers = utils.load_features(
            steps=[str(step)], suffix="bias.integral_buffer", **load_kwargs,
        )

    W_in = np.exp(-2 * wd * t) * W_0[layers[0]][f"step_{step_0}"] ** 2
    b_in = np.exp(-2 * wd * t) * b_0[layers[0]][f"step_{step_0}"] ** 2
    if i > 0:
        g_W = weight_buffers[layers[0]][f"step_{step}"]
        g_b = bias_buffers[layers[0]][f"step_{step}"]
        W_in += (lr ** 2) * np.exp(-2 * wd * t) * g_W
        b_in += (lr ** 2) * np.exp(-2 * wd * t) * g_b
    for layer in layers[1:]:
        W_out = np.exp(-2 * wd * t) * W_0[layer][f"step_{step_0}"] ** 2
        b_out = np.exp(-2 * wd * t) * b_0[layer][f"step_{step_0}"] ** 2
        if i > 0:
            g_W = weight_buffers[layer][f"step_{step}"]
            g_b = bias_buffers[layer][f"step_{step}"]
            W_out += (lr ** 2) * np.exp(-2 * wd * t) * g_W
            b_out += (lr ** 2) * np.exp(-2 * wd * t) * g_b
        theoretical[layer][step] = utils.out_synapses(W_out) - utils.in_synapses(
            W_in, b_in
        )
        W_in = W_out
        b_in = b_out


def compute_theoretical_momentum(
    step,
    layers,
    load_kwargs,
    theoretical,
    i,
    step_0,
    lr,
    wd,
    momentum,
    dampening,
    omega,
    gamma,
    W_0,
    b_0,
):
    t = lr * (1 - dampening) * step
    if i > 0:
        weight_buffers_1 = utils.load_features(
            steps=[str(step)], suffix="weight.integral_buffer_1", **load_kwargs,
        )
        bias_buffers_1 = utils.load_features(
            steps=[str(step)], suffix="bias.integral_buffer_1", **load_kwargs,
        )
        weight_buffers_2 = utils.load_features(
            steps=[str(step)], suffix="weight.integral_buffer_2", **load_kwargs,
        )
        bias_buffers_2 = utils.load_features(
            steps=[str(step)], suffix="bias.integral_buffer_2", **load_kwargs,
        )

    W_in = W_0[layers[0]][f"step_{step_0}"] ** 2
    b_in = b_0[layers[0]][f"step_{step_0}"] ** 2
    if i > 0:
        g_W_in_1 = weight_buffers_1[layers[0]][f"step_{step}"]
        g_b_in_1 = bias_buffers_1[layers[0]][f"step_{step}"]
        g_W_in_2 = weight_buffers_2[layers[0]][f"step_{step}"]
        g_b_in_2 = bias_buffers_2[layers[0]][f"step_{step}"]

    for layer in layers[1:]:
        W_out = W_0[layer][f"step_{step_0}"] ** 2
        b_out = b_0[layer][f"step_{step_0}"] ** 2

        # Homogenous solution
        if gamma < omega:
            cos = np.cos(np.sqrt(omega ** 2 - gamma ** 2) * t)
            sin = np.sin(np.sqrt(omega ** 2 - gamma ** 2) * t)
            scale = np.exp(-gamma * t) * (
                cos + gamma / np.sqrt(omega ** 2 - gamma ** 2) * sin
            )
        elif gamma == omega:
            scale = np.exp(-gamma * t) * (1 + gamma * t)
        else:
            alpha_p = -gamma + np.sqrt(gamma ** 2 - omega ** 2)
            alpha_m = -gamma - np.sqrt(gamma ** 2 - omega ** 2)
            numer = alpha_p * np.exp(alpha_m * t) - alpha_m * np.exp(alpha_p * t)
            denom = alpha_p - alpha_m
            scale = numer / denom

        theoretical[layer][step] = scale * (
            utils.out_synapses(W_out, dtype=np.float128)
            - utils.in_synapses(W_in, b_in, dtype=np.float128)
        )
        W_in = W_out
        b_in = b_out

        if i > 0:
            g_W_out_1 = weight_buffers_1[layer][f"step_{step}"]
            g_b_out_1 = bias_buffers_1[layer][f"step_{step}"]
            g_W_out_2 = weight_buffers_2[layer][f"step_{step}"]
            g_b_out_2 = bias_buffers_2[layer][f"step_{step}"]

            # Inhomogenous solution
            if gamma < omega:
                sqrt = np.sqrt(omega ** 2 - gamma ** 2)
                scale_1 = np.exp(-gamma * t) * np.sin(sqrt * t) / sqrt
                scale_2 = -np.exp(-gamma * t) * np.cos(sqrt * t) / sqrt

            elif gamma == omega:
                scale_1 = np.exp(-gamma * t) * t
                scale_2 = -np.exp(-gamma * t)

            else:
                sqrt = np.sqrt(gamma ** 2 - omega ** 2)
                alpha_p = -gamma + sqrt
                alpha_m = -gamma - sqrt
                scale_1 = np.exp(alpha_p * t) / (alpha_p - alpha_m)
                scale_2 = -np.exp(alpha_m * t) / (alpha_p - alpha_m)

            scale = (lr * (1 - dampening)) * 2

            if (
                np.all(np.isfinite(g_W_out_1))
                and np.all(np.isfinite(g_W_in_1))
                and np.all(np.isfinite(g_b_in_1))
            ):
                theoretical[layer][step] += (
                    scale
                    * scale_1
                    * (
                        utils.out_synapses(g_W_out_1, dtype=np.float128)
                        - utils.in_synapses(g_W_in_1, g_b_in_1, dtype=np.float128)
                    )
                )
            if (
                np.all(np.isfinite(g_W_out_2))
                and np.all(np.isfinite(g_W_in_2))
                and np.all(np.isfinite(g_b_in_2))
            ):
                theoretical[layer][step] += (
                    scale
                    * scale_2
                    * (
                        utils.out_synapses(g_W_out_2, dtype=np.float128)
                        - utils.in_synapses(g_W_in_2, g_b_in_2, dtype=np.float128)
                    )
                )

            g_W_in_1 = g_W_out_1
            g_b_in_1 = g_b_out_1
            g_W_in_2 = g_W_out_2
            g_b_in_2 = g_b_out_2


def rescale(model, feats_dir, steps, **kwargs):
    lr = kwargs.get("lr")
    wd = kwargs.get("wd")

    layers = [layer for layer in utils.get_layers(model) if "conv" in layer]
    W_0 = utils.load_features(
        steps=[str(steps[0])],
        feats_dir=feats_dir,
        model=model,
        suffix="weight",
        group="params",
    )
    b_0 = utils.load_features(
        steps=[str(steps[0])],
        feats_dir=feats_dir,
        model=model,
        suffix="bias",
        group="params",
    )

    load_kwargs = {
        "model": model,
        "feats_dir": feats_dir,
    }
    theory_kwargs = {
        "lr": lr,
        "wd": wd,
        "W_0": W_0,
        "b_0": b_0,
        "step_0": steps[0],
    }

    theoretical = {layer: {} for layer in layers[1:]}
    empirical = {layer: {} for layer in layers[1:]}
    for i in tqdm(range(len(steps))):
        step = steps[i]
        theory_kwargs["i"] = i
        load_kwargs["group"] = "buffers"
        compute_theoretical(step, layers, load_kwargs, theoretical, **theory_kwargs)
        load_kwargs["group"] = "params"
        compute_empirical(step, layers, load_kwargs, empirical)

    return {"empirical": empirical, "theoretical": theoretical}


def rescale_momentum(model, feats_dir, steps, **kwargs):
    lr = kwargs.get("lr")
    wd = kwargs.get("wd")
    momentum = kwargs.get("momentum")
    dampening = kwargs.get("dampening")

    lr = np.array(lr, dtype=np.float128)
    wd = np.array(wd, dtype=np.float128)
    momentum = np.array(momentum, dtype=np.float128)
    dampening = np.array(dampening, dtype=np.float128)

    denom = lr * (1 - dampening) * (1 + momentum)
    gamma = (1 - momentum) / denom
    omega = np.sqrt(4 * wd / denom)

    layers = [layer for layer in utils.get_layers(model) if "conv" in layer]
    W_0 = utils.load_features(
        steps=[str(steps[0])],
        feats_dir=feats_dir,
        model=model,
        suffix="weight",
        group="params",
    )
    b_0 = utils.load_features(
        steps=[str(steps[0])],
        feats_dir=feats_dir,
        model=model,
        suffix="bias",
        group="params",
    )

    load_kwargs = {
        "model": model,
        "feats_dir": feats_dir,
    }
    theory_kwargs = {
        "lr": lr,
        "wd": wd,
        "momentum": momentum,
        "dampening": dampening,
        "gamma": gamma,
        "omega": omega,
        "W_0": W_0,
        "b_0": b_0,
        "step_0": steps[0],
    }

    theoretical = {layer: {} for layer in layers[1:]}
    empirical = {layer: {} for layer in layers[1:]}
    for i in tqdm(range(len(steps))):
        step = steps[i]
        theory_kwargs["i"] = i
        load_kwargs["group"] = "buffers"
        compute_theoretical_momentum(
            step, layers, load_kwargs, theoretical, **theory_kwargs
        )
        load_kwargs["group"] = "params"
        compute_empirical(step, layers, load_kwargs, empirical)

    return {"empirical": empirical, "theoretical": theoretical}
