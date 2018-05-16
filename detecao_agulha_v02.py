from scipy import ndimage, misc, signal
import numpy as np
import pylab as plt

def rotate( dimensao , angle):
    slope = np.tan(np.deg2rad(angle))
    b = dimensao / 2 * (1 - slope)
    R = np.zeros((dimensao, dimensao), float)

    for x in range(dimensao):
        R[int(slope * x + b)][x] = 1.
        R[int(slope * x + b)+1][x] = 1.
        R[int(slope * x + b)-1][x] = 1.
        R[int(slope * x + b) + 2][x] = 1.
        R[int(slope * x + b) - 2][x] = 1.
    R = np.rot90(R)

    plt.figure('kernel ')
    plt.imshow(R)
    plt.gray()

    return R



def funcao_detecao_agulhas(name, threshold = 10., resize = 0.7, d_blur = 0.02 , N_linhas_verticais = 10, angle = 0 , grafico = "nao"):   #name corresponde ao nome da imagem a analisar ... deve conter o '.jpg'

    im = misc.imresize( np.uint8( ndimage.imread( name , flatten=True) ) , resize)     #reading image

    altura, largura = np.shape(im)
    dim = int(largura * d_blur + 1)  # dimensao da matriz de convolucao

    M = rotate(dim, angle)

    im = signal.convolve2d(im, M, mode="valid")  # convolucao (passo mais demorado)

    plt.figure('imagem_convoluida ')
    plt.imshow(im)
    plt.gray()

    picos = 0
    derivadas = []
    passo = int(np.shape(im)[0] / (N_linhas_verticais - 1))
    todos_picos = []

    for i in range(0, np.shape(im)[0], passo ) :   #percorrer todas as linhas verticais igualmente espacadas
        plot_profile = im[i]
        derivada  =  (np.diff(plot_profile))**2    # derivada do perfil duma linha vertical
        derivadas.append(derivada)
        noise = np.mean(derivada) + np.std(derivada)*threshold

        plt.figure(i)
        plt.plot(derivada)
        plt.plot(np.ones(len(derivada))*noise)

        lista_picos = np.where(derivada >= noise)[0]
        print(i, lista_picos)

        if len(lista_picos) > 0:
            picos += 1
            todos_picos.append([lista_picos, i / passo])
    print('numero de picos = ', picos, 'numero de testes = ', N_linhas_verticais)

    plt.show()
    if picos >= 0.9*N_linhas_verticais: # and suposto == "nao") or (picos < N_linhas_verticais and suposto == "sim"):    # Se passou do threshold em todas as linhas - sera defeito
        return 'agulha'
    else:
        False


if __name__ == "__main__":
    print(funcao_detecao_agulhas("8.jpg",grafico="sim"))