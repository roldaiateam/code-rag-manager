package tienda;

@RestController
@RequiredArgsConstructor
public class ProductsController {
    public void listar() {}
}

@Service
public class ProductsUseCaseImpl {
}

@Entity
public class ProductDb {
}

@RestControllerAdvice
public class GlobalExceptionHandler {
}

@Mapper(componentModel = "spring")
public interface ProductsMapper {
}

public interface ProductsRepository extends JpaRepository<ProductDb, Long>,
    JpaSpecificationExecutor<ProductDb> {
}

public interface ProductsUseCase {
}

public interface ProductsPort {
}

public class PlainClass {
}
