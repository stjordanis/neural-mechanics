import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import os
import numpy as np
import deepdish as dd
import utils
import glob
import json


def statistics(model, feats_dir, steps, lr, wd, normalize):
    layers = utils.get_layers(model)
    weights = utils.load_features(
        model=model, 
        feats_dir=feats_dir,
        group="weights",
        steps=[str(steps[0])]
    )
    biases = utils.load_features(
        model=model, 
        feats_dir=feats_dir,
        group="biases",
        steps=[str(steps[0])]
    )
    wl_0 = weights[layers[-1]][f"step_{steps[0]}"]
    bl_0 = biases[layers[-1]][f"step_{steps[0]}"]
    Wl_0 = np.column_stack((wl_0, bl_0))
    theoretical = []
    for i in range(len(steps)):
        t = 1.0 * lr * steps[i]
        alpha_p = (-1 + np.sqrt(1 - 2 * lr * wd)) / lr 
        alpha_m = (-1 - np.sqrt(1 - 2 * lr * wd)) / lr 
        numer = (alpha_p * np.exp(alpha_m * t) - alpha_m * np.exp(alpha_p * t))
        denom = (alpha_p - alpha_m)
        if normalize:
            theoretical.append(numer / denom) 
            # np.exp(-wd * t)s
        else:
            theoretical.append(numer / denom * np.sum(Wl_0, axis=0)) 
            # np.exp(-wd * t) * np.sum(Wl_0, axis=0)
            
    empirical = []
    for i in range(len(steps)):
        step = steps[i]
        weights = utils.load_features(
            model=model, 
            feats_dir=feats_dir,
            group="weights",
            steps=[str(step)]
        )
        biases = utils.load_features(
            model=model, 
            feats_dir=feats_dir,
            group="biases",
            steps=[str(step)]
        )
        if f"step_{step}" in weights[layers[0]].keys():
            wl_t = weights[layers[-1]][f"step_{step}"]
            bl_t = biases[layers[-1]][f"step_{step}"]
            Wl_t = np.column_stack((wl_t, bl_t))
            if normalize:
                empirical.append(np.sum(Wl_t, axis=0) / np.sum(Wl_0, axis=0))
            else:
                empirical.append(np.sum(Wl_t, axis=0))
        else:
            print(f"Feautres for step_{step} don't exist.")

    return (empirical, theoretical)


def main(args=None, axes=None):

    if args is not None:
        ARGS = args
    if ARGS.plot_dir is None:
        ARGS.plot_dir = ARGS.save_dir

    # load hyperparameters
    with open(f"{ARGS.plot_dir}/{ARGS.experiment}/{ARGS.expid}/args.json") as f:
        hyperparameters = json.load(f)

    # load cache or run statistics
    print(">> Loading weights...")
    cache_path = f"{ARGS.plot_dir}/{ARGS.experiment}/{ARGS.expid}/cache"
    utils.makedir_quiet(cache_path)
    cache_file = f"{cache_path}/translation.h5"
    if os.path.isfile(cache_file) and not ARGS.overwrite:
        print("   Loading from cache...")
        steps, empirical, theoretical = dd.io.load(cache_file)
    else:
        step_names = glob.glob(f"{ARGS.save_dir}/{ARGS.experiment}/{ARGS.expid}/feats/*.h5")
        steps = sorted([int(s.split(".h5")[0].split("step")[1]) for s in step_names])
        empirical, theoretical = statistics(
            model=hyperparameters['model'],
            feats_dir=f"{ARGS.save_dir}/{ARGS.experiment}/{ARGS.expid}/feats",
            steps=steps,
            lr=hyperparameters['lr'],
            wd=hyperparameters['weight_decay'],
            normalize=ARGS.normalize,
        )
        print(f"   Caching features to {cache_file}")
        dd.io.save(cache_file, (steps, empirical, theoretical))

    # create plot
    print(">> Plotting...")
    plt.rcParams["font.size"] = 18
    if axes is None:
        fig, axes = plt.subplots(figsize=(15, 15))

    # plot data
    axes.plot(steps[0 : len(empirical)], empirical, c="r", ls="-", alpha=0.1, label="empirical")
    axes.plot(
        steps[0 : len(theoretical)],
        theoretical,
        c="b",
        lw=3,
        ls="--",
        label="theoretical",
    )
    
    # axes labels and title
    axes.set_xlabel("timestep")
    axes.set_ylabel(f"projection")
    axes.title.set_text(
        f"Projection for translational parameters across time"
    )
    if ARGS.use_tex:
        axes.set_xlabel("timestep")
        axes.set_ylabel(r"$\langle W, \mathbb{1}\rangle$")
        axes.set_title(
            r"Projection for translational parameters across time"
        )

    if ARGS.legend:
        axes.legend()

    # save plot
    plot_path = f"{ARGS.plot_dir}/{ARGS.experiment}/{ARGS.expid}/img"
    utils.makedir_quiet(plot_path)
    plot_file = f"{plot_path}/translation{ARGS.image_suffix}.pdf"
    plt.savefig(plot_file)
    print(f">> Saving figure to {plot_file}")


# plot-specific args
def extend_parser(parser):
    parser.add_argument(
        "--normalize",
        type=bool,
        help="whether to normalize by initial condition",
        default=False,
    )
    return parser


if __name__ == "__main__":
    parser = utils.default_parser()
    parser = extend_parser(parser)
    ARGS = parser.parse_args()

    if ARGS.use_tex:
        from matplotlib import rc
        # For TeX usage in titles
        rc("font", **{"family": "sans-serif", "sans-serif": ["Helvetica"]})
        ## for Palatino and other serif fonts use:
        # rc('font',**{'family':'serif','serif':['Palatino']})
        rc("text", usetex=True)

    main(ARGS)
